"""Serialize the typed authoring tree into supported native trigger records."""
from dataclasses import dataclass
import hashlib
from uuid import UUID, uuid5

from .constants import (
    ClassId as C, NodeField as N, SettingsField as S, DataType as T,
    ListKind, IntegerFunction, BooleanFunction,
)
from .errors import ValidationError
from .expressions import Expr, as_condition, OwnedResourceRef, REFERENCE_ARGUMENT_KINDS
from .formats.binary import FieldTable, U32, U64, I32, encode_string
from .formats.rpk import ResourceRecord
from .schema import FUNCTIONS
from .profiles import DEFAULT_PROFILE, GameProfile


def _table(fields) -> bytes:
    return FieldTable(fields).write()


def _rows(records) -> bytes:
    # Native child list wrapper: object -> array -> indexed records.
    return _table({0: _table({1: _table({i: record.write() for i, record in enumerate(records)})})})


@dataclass(frozen=True)
class Trigger:
    """One global native trigger. ``once`` applies to this trigger globally,
    not once per player. Use player-specific state for per-player behavior.

    Top-level conditions are a native list. Do not assume short-circuiting;
    guard potentially invalid references with nested ``actions.when``.
    """
    key: str
    events: tuple[Expr, ...]
    actions: tuple[Expr, ...]
    conditions: tuple[Expr, ...] = ()
    once: bool = True
    comment: str = ""
    resource_id: int | None = None
    name: str | None = None
    setups: tuple[Expr, ...] = ()
    context: int = 1
    embedded: bool = False

    def __post_init__(self):
        # Accept ordinary lists at the public boundary but freeze the definition.
        for field in ("events", "actions", "conditions", "setups"):
            object.__setattr__(self, field, tuple(getattr(self, field)))
        if not self.key or (not self.events and not self.embedded):
            raise ValidationError("Trigger needs a stable key and at least one event")
        if any(not isinstance(e, Expr) or e.data_type != T.EVENT for e in self.events):
            raise ValidationError(f"{self.key}: events must contain event expressions")
        if any(not isinstance(a, Expr) or a.data_type != T.ACTION for a in self.actions):
            raise ValidationError(f"{self.key}: actions must contain action expressions")
        if any(not isinstance(a, Expr) or a.data_type != T.ACTION for a in self.setups):
            raise ValidationError(f"{self.key}: setups must contain supported action expressions")
        if self.context not in [1, 2] or (not self.embedded and self.context != 1):
            raise ValidationError("Supported contexts are global (1) and embedded story event (2)")
        object.__setattr__(self, "conditions", tuple(as_condition(c) for c in self.conditions))
        if type(self.once) is not bool:
            raise ValidationError("Trigger.once must be a Python bool")


@dataclass(frozen=True)
class Script(Trigger):
    """Embedded native script, not an independently registered RPK resource."""
    context: int = 2
    embedded: bool = True


class TriggerCompiler:
    """A fresh serializer per trigger gives every emitted node its own identity."""
    def __init__(self, mod_id: UUID, resource_id: int, profile: GameProfile = DEFAULT_PROFILE, bindings=None):
        self.mod_id, self.resource_id, self.sequence = mod_id, resource_id, 0
        self.profile = profile
        self.bindings = bindings or {}

    def _base(self, data_type: T, slot: int, children=()) -> dict:
        self.sequence += 1
        seed = f"{self.resource_id:016X}/{self.sequence}"
        identity = uuid5(self.mod_id, seed).bytes_le + hashlib.sha256(seed.encode()).digest()[:12] + bytes(4)
        return {N.SLOT: U32.pack(slot), N.CHILDREN: _rows(children), N.ENABLED: b"\x01",
                N.DATA_TYPE: U32.pack(data_type),
                N.IDENTITY: _table({0: U64.pack(self.resource_id), 10: identity})}

    def _list(self, kind: ListKind, values, slot=0, setup=False) -> ResourceRecord:
        if setup and kind == ListKind.ACTIONS:
            kind = ListKind.SETUPS
        fields = self._base(T.DATA_LIST, slot)
        fields.update({N.LIST_PROFILE: U32.pack(2),
                       N.VALUE: _rows(self.expression(v, setup=setup) for v in values), N.LIST_KIND: U32.pack(kind)})
        return ResourceRecord(C.TRIGGER_LIST, FieldTable(fields))

    def _preset(self, class_id, data_type, value, slot) -> ResourceRecord:
        fields = self._base(data_type, slot)
        fields[N.VALUE] = value
        return ResourceRecord(class_id, FieldTable(fields))

    def expression(self, expr: Expr, slot: int = 0, setup=False) -> ResourceRecord:
        if expr.data_type == T.DATA_LIST:
            kind, values = expr.value
            return self._list(kind, values, slot, setup)
        if expr.function:
            if expr.function not in self.profile.functions:
                raise ValidationError(f"Function {expr.function} is unavailable in profile {self.profile.key}")
            spec = self.profile.functions[expr.function]
            # Revalidate even manually constructed Expr instances.
            if expr.data_type != spec.data_type or len(expr.arguments) != len(spec.parameters):
                raise ValidationError(f"Malformed expression: {expr.function}")
            if any(arg.data_type != p.data_type for arg, p in zip(expr.arguments, spec.parameters)):
                raise ValidationError(f"Parameter type mismatch: {expr.function}")
            for parameter, argument in zip(spec.parameters, expr.arguments):
                expected_kind = REFERENCE_ARGUMENT_KINDS.get(expr.function, {}).get(parameter.name)
                if expected_kind and argument.data_type == T.RESOURCE_LINK:
                    ref = argument.value
                    if isinstance(ref, OwnedResourceRef):
                        if ref.key not in self.bindings:
                            raise ValidationError(f"Unresolved owned resource: {ref.key}")
                        ref = self.bindings[ref.key]
                    if ref.kind not in ("other", expected_kind):
                        raise ValidationError(f"{expr.function}.{parameter.name} needs {expected_kind}, got {ref.kind}")
            children = [self.expression(value, index + 1, setup) for index, value in enumerate(expr.arguments)]
            output_type = spec.data_type
            if setup and output_type == T.ACTION:
                if not 0 <= spec.function_id <= 12:
                    raise ValidationError("Only verified native setup counterparts (IDs 0..12) are supported")
                output_type = T.SETUP
            fields = self._base(output_type, slot, children)
            fields[N.FUNCTION] = U32.pack(spec.function_id)
            return ResourceRecord(C.TRIGGER_CALL, FieldTable(fields))
        if expr.data_type == T.COMPARISON:
            return self._preset(C.COMPARISON_PRESET, T.COMPARISON, U32.pack(expr.value), slot)
        if expr.data_type == T.VARIABLE_NAME_PRESET:
            return self._preset(C.VARIABLE_NAME_PRESET, T.VARIABLE_NAME_PRESET, encode_string(expr.value), slot)
        if expr.data_type == T.LOCALIZED_STRING_LINK_PRESET:
            from .resources import ResourceContext
            context = ResourceContext(self.bindings, self.profile)
            fields = self._base(T.LOCALIZED_STRING_LINK_PRESET, slot)
            fields[C.LOCALIZED_LINK_PRESET] = _table({0: context.localized(expr.value)})
            return ResourceRecord(C.LOCALIZED_LINK_PRESET, FieldTable(fields))
        if expr.data_type == T.RESOURCE_LINK:
            ref = expr.value
            if isinstance(ref, OwnedResourceRef):
                if ref.key not in self.bindings:
                    raise ValidationError(f"Unresolved owned resource: {ref.key}")
                ref = self.bindings[ref.key]
            link = _table({20: encode_string(ref.url), 22: U64.pack(ref.resource_id), 23: encode_string(ref.name)})
            return self._preset(C.RESOURCE_LINK_PRESET, T.RESOURCE_LINK, link, slot)
        literal_profiles = {
            T.INTEGER: (C.INTEGER_PRESET, T.INTEGER_PRESET, I32.pack, IntegerFunction.PRESET),
            T.BOOLEAN: (C.BOOLEAN_PRESET, T.BOOLEAN_PRESET, lambda v: bytes([v]), BooleanFunction.PRESET),
            T.STRING: (C.STRING_PRESET, T.STRING_PRESET, encode_string, 0),
        }
        if expr.data_type not in literal_profiles:
            raise ValidationError(f"No literal serializer for {expr.data_type.name}")
        cid, preset_type, encode, function_id = literal_profiles[expr.data_type]
        preset = self._preset(cid, preset_type, encode(expr.value), 1)
        fields = self._base(expr.data_type, slot, [preset])
        fields[N.FUNCTION] = U32.pack(function_id)
        return ResourceRecord(C.TRIGGER_CALL, FieldTable(fields))

    def compile_script(self, trigger: Trigger) -> bytes:
        """Compile phases, including distinct setup node types, into settings."""
        settings = _table({
            S.CONTEXT: U32.pack(trigger.context), S.ONCE: bytes([trigger.once]),
            S.ENABLED: b"\x01", S.ACTIVE: b"\x01", S.COMMENT: encode_string(trigger.comment),
            S.EVENTS: self._list(ListKind.EVENTS, trigger.events).table.write(),
            S.CONDITIONS: self._list(ListKind.CONDITIONS, trigger.conditions).table.write(),
            S.ACTIONS: self._list(ListKind.ACTIONS, trigger.actions).table.write(),
            S.SETUPS: self._list(ListKind.SETUPS, trigger.setups, setup=True).table.write(),
        })
        # The native script resource contains a settings object in class field 0.
        return _table({C.TRIGGER_SETTINGS: settings})

    def compile(self, trigger: Trigger, *, resource_id: int, index: int) -> ResourceRecord:
        script = self.compile_script(trigger)
        return ResourceRecord.create(C.TRIGGER, resource_id, trigger.name or trigger.key, index,
                                     {C.TRIGGER: _table({0: script})})
