"""Scoped comparison of script meaning and the untouched RPK envelope.

Comparison is independent of Python generation. Only known table framing and
generated node identity bytes are ignored; parent IDs and all other data remain.
"""
from ..constants import ClassId as C
from ..formats.binary import FieldTable
from ..formats.rpk import ResourcePack, ResourceRecord
from ..profiles import DEFAULT_PROFILE
from .reader import decode_pack


def normalized_node(pack, node):
    skip = {2, 7}
    if node.kind == "list" or node.data_type == 31:
        skip.add(20)
    if node.data_type == 133:
        skip.add(int(C.LOCALIZED_LINK_PRESET))
    scalar = {key: pack.source_bytes(origin.span).hex() for key, origin in node.fields.items() if key not in skip}
    value = node.value
    if node.data_type == 31 and isinstance(value, dict):
        value = {key: value[key] for key in ("resource_id", "url", "name")}
    # Localized metadata retains exact bytes, not just a rendered text key.
    return dict(class_id=node.class_id, data_type=node.data_type, slot=node.slot,
                enabled=node.enabled, function_id=node.function_id, list_kind=node.list_kind,
                parent_resource_id=node.parent_resource_id, scalars=scalar, value=value,
                children=[normalized_node(pack, n) for n in node.children],
                auxiliary_children=[normalized_node(pack, n) for n in node.auxiliary_children])


def normalized_script(pack, script):
    # Settings directory framing may change, but all scalar values must match.
    scalars = {key: pack.source_bytes(origin.span).hex() for key, origin in script.fields.items()
               if key not in (11, 12, 13, 14)}
    return dict(resource_id=script.resource_id, resource_name=script.resource_name,
                role=script.role, settings=scalars, choice=script.choice,
                phases={name: normalized_node(pack, root) for name, root in script.phases.items()})


def _masked_record(record):
    fields = dict(record.table.fields)
    if record.class_id == C.TRIGGER:
        holder = FieldTable.read(fields[C.TRIGGER]).fields
        fields[C.TRIGGER] = {key: b"<script>" if key == 0 else value for key, value in holder.items()}
    elif record.class_id == C.STORY_EVENT:
        base = FieldTable.read(fields[C.STORY_EVENT_BASE]).fields
        fields[C.STORY_EVENT_BASE] = {key: b"<script>" if key == 1 else value for key, value in base.items()}
        event = FieldTable.read(fields[C.STORY_EVENT]).fields
        holder = FieldTable.read(event[4]).fields
        groups = FieldTable.read(holder[1]).fields
        rows = FieldTable.read(groups[1]).fields
        choices = []
        for index, raw in rows.items():
            choice = ResourceRecord.read(raw)
            choices.append((index, choice.class_id, {key: b"<script>" if key in (2, 6) else value
                                                     for key, value in choice.table.fields.items()}))
        fields[C.STORY_EVENT] = {**event, 4: {**holder, 1: {**groups, 1: choices}}}
    return record.class_id, fields


def envelope(data, profile=DEFAULT_PROFILE):
    """Mask only registered script fields; retain every other value/order."""
    pack = ResourcePack.read(data, profile=profile)
    stores = []
    for store_id, store in pack.stores():
        groups = FieldTable.read(store.manager.fields[21])
        values = []
        for group_id, raw in groups.fields.items():
            records = FieldTable.read(raw)
            values.append((group_id, [(index, _masked_record(ResourceRecord.read(value)))
                                      for index, value in records.fields.items()]))
        stores.append((store_id, store.prefix, {**store.manager.fields, 21: values}))
    # Header length is the only expected variable header field.
    return pack.prefix[:12]+pack.prefix[16:], {**pack.table.fields, 13: stores}


def compare_trigger_packs(before: bytes, after: bytes, *, profile=DEFAULT_PROFILE):
    """Return scoped offline equality; does not claim engine equivalence."""
    a, b = decode_pack(before, profile=profile), decode_pack(after, profile=profile)
    old = {(s.resource_id, s.role): s for s in a.scripts}
    new = {(s.resource_id, s.role): s for s in b.scripts}
    same_inventory = list(old) == list(new) and len(a.scripts) == len(b.scripts)
    differing = []
    if same_inventory:
        for key in old:
            if normalized_script(a, old[key]) != normalized_script(b, new[key]):
                differing.append({"resource_id": key[0], "role": key[1]})
    same_envelope = envelope(before, profile) == envelope(after, profile)
    diagnostics_clear = not a.diagnostics and not b.diagnostics
    return dict(equivalent=same_inventory and same_envelope and not differing and diagnostics_clear,
                scope="Registered triggers and all nonscript envelope values",
                script_inventory_equal=same_inventory, scripts_compared=len(old) if same_inventory else 0,
                nodes_before=a.statistics["nodes"], nodes_after=b.statistics["nodes"],
                nonscript_envelope_equal=same_envelope, differing_scripts=differing,
                ignored_differences=["Known table directory framing", "Generated node identity bytes; parent resource IDs are compared", "RPK payload length header"],
                input_diagnostics=len(a.diagnostics), rebuilt_diagnostics=len(b.diagnostics),
                runtime_tested=False)
