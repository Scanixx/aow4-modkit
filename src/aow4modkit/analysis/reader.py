"""Bounded SDK-only decoder for global and embedded story-event triggers.

Container values are decoded only at registered locations. Original bytes and
exact ranges remain available, including unknown fields and executable nodes.
"""
import hashlib
from pathlib import Path

from ..constants import (ClassId as C, DataType as T, NodeField as N, ResourceField as R,
                         StoryEventBaseField, StoryEventField, StoryChoiceField)
from ..errors import FormatError
from ..formats.binary import FieldTable, U32, U64, I32, decode_string
from ..formats.rpk import ResourcePack
from ..profiles import DEFAULT_PROFILE
from .model import DecodeLimits, Diagnostic, FieldOrigin, Node, Script, DecodedPack
from .signatures import reverse_signatures

PHASES = {11: ("events", 0), 12: ("conditions", 1), 13: ("actions", 3), 14: ("setups", 2)}
STORY_EVENT = C.STORY_EVENT
STORY_BASE = C.STORY_EVENT_BASE
STORY_CHOICE = C.STORY_EVENT_CHOICE
COMMON_NODE_FIELDS = {0, 2, 3, 5, 7}
PRESETS = {int(C.COMPARISON_PRESET): 7, int(C.INTEGER_PRESET): 9,
           int(C.BOOLEAN_PRESET): 11, int(C.STRING_PRESET): 18,
           int(C.VARIABLE_NAME_PRESET): 26, int(C.RESOURCE_LINK_PRESET): 31,
           int(C.LOCALIZED_LINK_PRESET): 133}


class _Decoder:
    def __init__(self, raw, profile, limits):
        self.raw, self.profile, self.limits = raw, profile, limits
        self.signatures = reverse_signatures(profile)
        self.diagnostics, self.scripts, self.resources = [], [], []
        self.node_count = self.fields_read = self.parsed_bytes = 0
        self.unknown_nodes = self.disabled_nodes = self.duplicate_identities = 0
        self.identities, self.refs, self.resource_ids = {}, {}, set()

    def issue(self, code, path, message, span=None, severity="warning"):
        if len(self.diagnostics) >= self.limits.max_diagnostics:
            raise FormatError("Analysis diagnostic limit exceeded")
        self.diagnostics.append(Diagnostic(code, severity, path, message, span))

    def table(self, raw, base, offset=0):
        self.parsed_bytes += len(raw) - offset
        if self.parsed_bytes > self.limits.max_parsed_bytes:
            raise FormatError("Analysis cumulative parsed-byte limit exceeded")
        result = FieldTable.read(raw, offset)
        self.fields_read += len(result.fields)
        if self.fields_read > self.limits.max_fields:
            raise FormatError("Analysis field limit exceeded")
        return result

    @staticmethod
    def at(table, field, base):
        if field not in table.fields:
            raise FormatError(f"Missing required field {field}")
        return table.fields[field], base + table.field_spans[field][0]

    def origins(self, table, base):
        return {key: FieldOrigin((base + table.field_spans[key][0], base + table.field_spans[key][1]),
                                 len(value), hashlib.sha256(value).hexdigest())
                for key, value in table.fields.items()}

    def number(self, table, field, path, size=4, required=True):
        value = table.fields.get(field)
        if value is None:
            if required:
                self.issue("MISSING_FIELD", path, f"Missing numeric field {field}", severity="error")
            return None
        if len(value) != size:
            self.issue("INVALID_SCALAR", path, f"Field {field} must occupy {size} bytes", severity="error")
            return None
        return int.from_bytes(value, "little")

    def flag(self, table, field, path):
        value = self.number(table, field, path, size=1)
        if value is not None and value not in (0, 1):
            self.issue("INVALID_BOOLEAN", path, f"Field {field} is not a native boolean", severity="error")
            return None
        return None if value is None else bool(value)

    def text(self, table, field, path, required=True):
        if field not in table.fields:
            if required:
                self.issue("MISSING_FIELD", path, f"Missing text field {field}", severity="error")
            return None
        try:
            return decode_string(table.fields[field])
        except FormatError as exc:
            self.issue("INVALID_STRING", path, str(exc), severity="error")
            return None

    def rows(self, raw, base):
        outer = self.table(raw, base)
        if not outer.fields:
            return []
        if set(outer.fields) != {0}:
            raise FormatError("Unknown native child-store wrapper")
        data, at = self.at(outer, 0, base)
        groups = self.table(data, at)
        if set(groups.fields) != {1}:
            raise FormatError("Unknown native child-group wrapper")
        data, at = self.at(groups, 1, at)
        entries = self.table(data, at)
        return [(key, *self.at(entries, key, at)) for key in entries.fields]

    def link(self, raw, base, path):
        table = self.table(raw, base)
        uid = self.number(table, 22, path, size=8)
        value = dict(resource_id=f"{uid:016X}" if uid is not None else None,
                     url=self.text(table, 20, path), name=self.text(table, 23, path))
        value["scope"] = "internal" if uid is not None and uid in self.resource_ids else "external_origin_unresolved"
        self.refs.setdefault((uid, value["url"], value["name"]), value)
        if set(table.fields) != {20, 22, 23}:
            self.issue("EXTRA_LINK_FIELDS", path, "Link contains fields beyond the supported schema")
        return value

    def localized(self, raw, base, path):
        outer = self.table(raw, base)
        if 0 in outer.fields:
            inner, at = self.at(outer, 0, base)
            table = self.table(inner, at)
        else:
            table = outer
        # Keep exact formatter bytes; do not pretend to have the MO translation.
        return dict(key=self.text(table, 1, path), original_hex=raw.hex(), translation_resolved=False)

    def node(self, raw, base, path, owner, depth=0, implicit_class=None):
        if depth > self.limits.max_depth:
            raise FormatError("Trigger nesting depth limit exceeded")
        self.node_count += 1
        if self.node_count > self.limits.max_nodes:
            raise FormatError("Trigger node limit exceeded")
        if implicit_class is None and len(raw) < 5:
            raise FormatError("Truncated trigger node")
        cid = implicit_class if implicit_class is not None else U32.unpack_from(raw)[0]
        table = self.table(raw, base, 0 if implicit_class is not None else 4)
        if cid not in PRESETS and cid not in (C.TRIGGER_LIST, C.TRIGGER_CALL):
            # Unknown inheritance is not evidence for any common field layout.
            self.unknown_nodes += 1
            self.issue("UNKNOWN_NODE_CLASS", path, f"Unregistered node class {cid:08X}", (base, base+len(raw)))
            return Node(path, (base, base+len(raw)), cid, None, None, None,
                        "unknown", self.origins(table, base), unknown_fields=tuple(table.fields))
        typ = self.number(table, N.DATA_TYPE, path)
        node = Node(path, (base, base+len(raw)), cid, typ,
                    self.number(table, N.SLOT, path), self.flag(table, N.ENABLED, path),
                    "unknown", self.origins(table, base))
        if node.enabled is False:
            self.disabled_nodes += 1
        if N.IDENTITY in table.fields:
            data, at = self.at(table, N.IDENTITY, base)
            identity = self.table(data, at)
            if set(identity.fields) != {0, 10}:
                self.issue("UNKNOWN_IDENTITY_FIELDS", path, "Identity has fields beyond the observed parent/identity schema", node.span)
            parent = self.number(identity, 0, path, size=8)
            node.parent_resource_id = f"{parent:016X}" if parent is not None else None
            node.identity = identity.fields.get(10, b"").hex()
            if parent != owner:
                self.issue("NODE_PARENT_MISMATCH", path, "Serialized parent does not match containing resource", node.span)
            if len(identity.fields.get(10, b"")) != 32:
                self.issue("UNKNOWN_IDENTITY_LAYOUT", path, "Expected 32 node identity bytes", node.span)
            signature = (parent, node.identity)
            if signature in self.identities:
                self.duplicate_identities += 1
            else:
                self.identities[signature] = path
        else:
            self.issue("MISSING_NODE_IDENTITY", path, "Node identity field is absent", node.span)
        allowed = set(COMMON_NODE_FIELDS)
        if cid == C.TRIGGER_LIST:
            node.kind = "list"
            if typ != T.DATA_LIST:
                self.issue("LIST_TYPE_MISMATCH", path, "List node does not have DATA_LIST type", node.span, "error")
            allowed |= {6, 20, 21}
            node.list_kind = self.number(table, N.LIST_KIND, path)
            if node.list_kind not in (0, 1, 2, 3):
                self.issue("UNKNOWN_LIST_KIND", path, f"Unknown list kind {node.list_kind}", node.span)
            if self.number(table, N.LIST_PROFILE, path) != 2:
                self.issue("UNKNOWN_LIST_PROFILE", path, "List profile differs from observed value 2", node.span)
            data, at = self.at(table, N.VALUE, base)
            node.children = [self.node(value, pos, f"{path}/item[{key}]", owner, depth+1)
                             for key, value, pos in self.rows(data, at)]
            expected_type = {0: 0, 1: 1, 2: 2, 3: 3}.get(node.list_kind)
            for child in node.children:
                if expected_type is not None and child.data_type is not None and child.data_type != expected_type:
                    self.issue("LIST_ITEM_TYPE_MISMATCH", child.path, f"List kind {node.list_kind} expects native type {expected_type}, found {child.data_type}", child.span, "error")
        elif cid == C.TRIGGER_CALL:
            node.kind = "call"
            allowed.add(1)
            node.function_id = self.number(table, N.FUNCTION, path)
            entry = self.signatures.get((typ, node.function_id))
            if entry:
                spec, node.aliases = entry
                node.function_name = spec.name
            else:
                self.unknown_nodes += 1
                self.issue("UNKNOWN_FUNCTION", path, f"Unregistered signature {typ}:{node.function_id}", node.span)
        elif cid in PRESETS:
            node.kind = "preset"
            if typ != PRESETS[cid]:
                self.issue("PRESET_TYPE_MISMATCH", path, "Preset class and data type disagree", node.span, "error")
            if cid == C.LOCALIZED_LINK_PRESET:
                allowed.add(int(cid))
                data, at = self.at(table, cid, base)
                holder = self.table(data, at)
                data, at = self.at(holder, 0, at)
                node.value = self.localized(data, at, path)
                if set(holder.fields) != {0}:
                    self.issue("EXTRA_LOCALIZED_PRESET_FIELDS", path, "Localized preset wrapper has extra fields", node.span)
            else:
                allowed.add(20)
                data, at = self.at(table, N.VALUE, base)
                if typ in (7, 9):
                    if len(data) != 4:
                        raise FormatError("Integer/comparison preset must occupy four bytes")
                    node.value = I32.unpack(data)[0]
                    if typ == 7 and node.value not in (10, 12):
                        self.issue("UNNAMED_COMPARISON_OPERATOR", path, f"Comparison operator {node.value} has no supported name", node.span)
                elif typ == 11:
                    if data not in (b"\x00", b"\x01"):
                        raise FormatError("Malformed boolean preset")
                    node.value = bool(data[0])
                elif typ in (18, 26):
                    node.value = decode_string(data)
                elif typ == 31:
                    node.value = self.link(data, at, path)
        else:
            self.unknown_nodes += 1
            self.issue("UNKNOWN_NODE_CLASS", path, f"Unregistered node class {cid:08X}", node.span)
        # Parse child stores only for registered classes. An unknown class may
        # use field 2 differently; its exact bytes remain available by span.
        if N.CHILDREN in table.fields and (cid in PRESETS or cid in (C.TRIGGER_CALL, C.TRIGGER_LIST)):
            data, at = self.at(table, N.CHILDREN, base)
            args = [self.node(value, pos, f"{path}/argument[{key}]", owner, depth+1)
                    for key, value, pos in self.rows(data, at)]
            if cid == C.TRIGGER_CALL:
                node.children = args
                slots = [arg.slot for arg in args]
                if len(set(slots)) != len(slots):
                    self.issue("DUPLICATE_ARGUMENT_SLOT", path, "Function argument slots are duplicated", node.span, "error")
                if entry:
                    parameters = {i: p for i, p in enumerate(spec.parameters, 1)}
                    if set(slots) != set(parameters) or len(args) != len(parameters):
                        self.issue("ARGUMENT_SLOTS_MISMATCH", path, "Arguments differ from the registered signature", node.span, "error")
                    for arg in args:
                        param = parameters.get(arg.slot)
                        if param:
                            arg.parameter_name = param.name
                            if arg.data_type != param.data_type:
                                self.issue("ARGUMENT_TYPE_MISMATCH", arg.path, f"{param.name} expects {param.data_type.name}, got {arg.data_type}", arg.span, "error")
            else:
                node.auxiliary_children = args
                if args:
                    self.issue("AUXILIARY_CHILDREN", path, "Non-call node contains additional base children", node.span)
        elif cid == C.TRIGGER_CALL:
            self.issue("MISSING_ARGUMENT_STORE", path, "Call has no child store", node.span, "error")
        node.unknown_fields = tuple(sorted(set(table.fields)-allowed))
        if node.unknown_fields:
            self.issue("UNKNOWN_NODE_FIELDS", path, f"Uninterpreted fields: {node.unknown_fields}", node.span)
        return node

    def script(self, raw, base, path, owner, name, role, choice=None):
        outer = self.table(raw, base)
        data, at = self.at(outer, C.TRIGGER_SETTINGS, base)
        settings = self.table(data, at)
        phases = {}
        for field, (label, expected) in PHASES.items():
            data, pos = self.at(settings, field, at)
            phases[label] = self.node(data, pos, path+"/"+label, owner, implicit_class=int(C.TRIGGER_LIST))
            if phases[label].list_kind != expected:
                self.issue("PHASE_KIND_MISMATCH", path+"/"+label, "Native phase has the wrong list kind", phases[label].span, "error")
        known = {0, 2, 3, 4, 5, *PHASES}
        if set(settings.fields)-known or set(outer.fields) != {int(C.TRIGGER_SETTINGS)}:
            self.issue("UNKNOWN_SCRIPT_FIELDS", path, "Script/settings contain fields beyond the supported schema", (base, base+len(raw)))
        context = self.number(settings, 0, path)
        expected_context = 1 if role == "global" else 2
        if context != expected_context:
            self.issue("UNEXPECTED_SCRIPT_CONTEXT", path, f"Locator expects context {expected_context}, found {context}", (base, base+len(raw)))
        self.scripts.append(Script(path, (base, base+len(raw)), f"{owner:016X}", name, role,
                                   self.origins(settings, at), context,
                                   self.flag(settings, 2, path), self.flag(settings, 3, path),
                                   self.flag(settings, 4, path), self.text(settings, 5, path), phases, choice))

    def resource_scripts(self, table, base, path, owner, name, cid):
        if cid == C.TRIGGER:
            data, at = self.at(table, C.TRIGGER, base)
            holder = self.table(data, at)
            if set(holder.fields) != {0}:
                self.issue("UNKNOWN_SCRIPT_HOLDER_FIELDS", path, "Global trigger holder contains additional fields")
            data, at = self.at(holder, 0, at)
            self.script(data, at, path+"/global", owner, name, "global")
        elif cid == STORY_EVENT:
            data, at = self.at(table, STORY_BASE, base)
            event = self.table(data, at)
            data, at = self.at(event, StoryEventBaseField.INITIALIZATION, at)
            self.script(data, at, path+"/initialization", owner, name, "initialization")
            data, at = self.at(table, STORY_EVENT, base)
            event = self.table(data, at)
            data, at = self.at(event, StoryEventField.CHOICES, at)
            holder = self.table(data, at)
            if set(holder.fields) != {0, 1}:
                self.issue("UNKNOWN_CHOICE_LIST_FIELDS", path, "Choice list contains additional fields")
            next_id = self.number(holder, 0, path, size=1)
            data, at = self.at(holder, 1, at)
            groups = self.table(data, at)
            if set(groups.fields) != {1}:
                raise FormatError("Unknown story-event choice group")
            data, at = self.at(groups, 1, at)
            rows = self.table(data, at)
            seen = set()
            for index in rows.fields:
                data, pos = self.at(rows, index, at)
                if len(data) < 5 or U32.unpack_from(data)[0] != STORY_CHOICE:
                    raise FormatError("Unknown story-event choice class")
                choice_path = f"{path}/choice[{index}]"
                button = self.table(data, pos, 4)
                identifier = self.number(button, StoryChoiceField.LIST_ID, choice_path, size=1)
                if identifier in seen:
                    self.issue("DUPLICATE_CHOICE_ID", choice_path, "Choice ID is duplicated", severity="error")
                seen.add(identifier)
                text, text_at = self.at(button, StoryChoiceField.TEXT, pos)
                category, category_at = self.at(button, StoryChoiceField.CATEGORY, pos)
                choice = dict(index=index, list_id=identifier, next_free_id=next_id,
                              visibility_mode=self.number(button, StoryChoiceField.VISIBILITY_MODE, choice_path),
                              text=self.localized(text, text_at, choice_path),
                              category=self.link(category, category_at, choice_path))
                if set(button.fields) != {0, 2, 3, 4, 5, 6}:
                    self.issue("UNKNOWN_CHOICE_FIELDS", choice_path, "Choice has fields beyond the supported schema")
                for field, role in [(StoryChoiceField.ACTION, "action"), (StoryChoiceField.VISIBILITY, "visibility")]:
                    script, start = self.at(button, field, pos)
                    self.script(script, start, choice_path+"/"+role, owner, name,
                                f"choice[{index}].{role}", choice)
            if seen and (next_id is None or next_id <= max(seen)):
                self.issue("INVALID_NEXT_CHOICE_ID", path, "Next free choice ID does not exceed allocated IDs", severity="error")

    def decode(self):
        pack = ResourcePack.read(self.raw, profile=self.profile)
        self.parsed_bytes += len(self.raw)
        self.fields_read += len(pack.table.fields)
        if self.parsed_bytes > self.limits.max_parsed_bytes or self.fields_read > self.limits.max_fields:
            raise FormatError("Analysis root-table budget exceeded")
        stores_raw, at = self.at(pack.table, 13, 0)
        stores = self.table(stores_raw, at)
        located = []
        for store_id in stores.fields:
            store_raw, store_at = self.at(stores, store_id, at)
            size = len(self.profile.store_headers[0])
            if store_raw[:size] not in self.profile.store_headers:
                raise FormatError("Unsupported content-store header")
            store = self.table(store_raw, store_at, size)
            data, pos = self.at(store, 21, store_at)
            groups = self.table(data, pos)
            for group_id in groups.fields:
                data, group_at = self.at(groups, group_id, pos)
                records = self.table(data, group_at)
                for index in records.fields:
                    if len(located) >= self.limits.max_resources:
                        raise FormatError("Resource count limit exceeded")
                    raw, start = self.at(records, index, group_at)
                    if len(raw) < 5:
                        raise FormatError("Truncated resource record")
                    table = self.table(raw, start, 4)
                    cid = U32.unpack_from(raw)[0]
                    path = f"store[{store_id}]/group[{group_id}]/record[{index}]"
                    owner = self.number(table, R.ID, path, size=8)
                    name = self.text(table, R.NAME, path)
                    if owner in self.resource_ids:
                        self.issue("DUPLICATE_RESOURCE_ID", path, "Resource identity is duplicated", severity="error")
                    if owner is not None:
                        self.resource_ids.add(owner)
                    resource = dict(path=path, span=(start, start+len(raw)), class_id=cid,
                                    resource_id=f"{owner:016X}" if owner is not None else None,
                                    name=name, url=self.text(table, R.URL, path),
                                    enabled=self.flag(table, R.ENABLED, path), fields=self.origins(table, start),
                                    script_locator_supported=cid in (C.TRIGGER, STORY_EVENT), script_indices=[])
                    self.resources.append(resource)
                    located.append((table, start, path, owner, name, cid))
        for resource, args in zip(self.resources, located):
            first = len(self.scripts)
            if args[3] is None:
                self.issue("UNDECODABLE_RESOURCE_ID", args[2], "Cannot assign script provenance to an invalid resource ID", severity="error")
            else:
                self.resource_scripts(*args)
            resource["script_indices"] = list(range(first, len(self.scripts)))
        return pack


def decode_pack(data: bytes, *, source_name="input.rpk", profile=DEFAULT_PROFILE, limits=None):
    """Decode data, never execute it. Unsupported semantics produce diagnostics.

    Malformed binary framing or exhausted limits raise FormatError. Coverage
    concerns registered script locations, not every field of every resource.
    """
    limits = limits or DecodeLimits()
    if not isinstance(data, bytes):
        raise TypeError("decode_pack expects immutable bytes")
    if len(data) > limits.max_input_bytes:
        raise FormatError("RPK input exceeds analysis size limit")
    decoder = _Decoder(data, profile, limits)
    pack = decoder.decode()
    statistics = dict(resources=len(decoder.resources), scripts=len(decoder.scripts),
                      nodes=decoder.node_count, unknown_nodes=decoder.unknown_nodes,
                      disabled_nodes=decoder.disabled_nodes, duplicate_node_identities=decoder.duplicate_identities,
                      resources_with_script_locators=sum(r["script_locator_supported"] for r in decoder.resources),
                      resources_inventoried_only=sum(not r["script_locator_supported"] for r in decoder.resources),
                      parsed_bytes=decoder.parsed_bytes, fields_read=decoder.fields_read,
                      errors=sum(d.severity == "error" for d in decoder.diagnostics),
                      warnings=sum(d.severity == "warning" for d in decoder.diagnostics))
    # A caller-supplied name is display metadata, not a path to execute or write.
    source_name = str(source_name).replace("\\", "/").rsplit("/", 1)[-1]
    return DecodedPack(source_name, hashlib.sha256(data).hexdigest(), len(data), profile.key,
                       pack.dependencies, decoder.resources, decoder.scripts, decoder.diagnostics,
                       list(decoder.refs.values()), statistics, _input_bytes=data)


def read_pack(path, *, profile=DEFAULT_PROFILE, limits=None):
    """Read a selected RPK file with a bounded read; never inspect processes."""
    limits = limits or DecodeLimits()
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(limits.max_input_bytes+1)
    return decode_pack(raw, source_name=path.name, profile=profile, limits=limits)
