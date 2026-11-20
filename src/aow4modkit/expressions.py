"""Typed immutable Python definitions; these objects are not executed by AoW4."""
from dataclasses import dataclass
from typing import Any

from .compatibility import DlcRequirement
from .constants import DataType as T, ListKind, ComparisonOperator
from .errors import ValidationError
from .schema import FUNCTIONS

REFERENCE_ARGUMENT_KINDS = {
    "players.has_property": {"property": "side_property"},
    "actions.add_property": {"property": "side_property"},
    "actions.add_transformation": {"transformation": "racial_transformation"},
    "races.has_transformation": {"transformation": "racial_transformation"},
    "tokens.definition": {"token": "token"},
    "actions.give_token": {"token": "token"},
}


@dataclass(frozen=True)
class ResourceRef:
    """A complete external link. Declaring DLC does not require installing it.

    ``pack`` is the exact native RPK filename. ``url`` must be the actual
    resource URL, obtainable with the read-only inspect command. Numeric IDs
    alone do not supply the resource's schema or contents.
    """
    resource_id: int
    name: str
    url: str
    pack: str
    dlc: DlcRequirement | None = None
    kind: str = "other"

    def __post_init__(self):
        if type(self.resource_id) is not int or not 0 < self.resource_id <= 0xFFFFFFFFFFFFFFFF:
            raise ValidationError("Resource ID must be a nonzero unsigned 64-bit integer")
        if not self.name or not self.pack or any(c in self.pack for c in "/\\\x00"):
            raise ValidationError("External reference needs a name and a pack filename")
        if not self.url.upper().startswith(f"[#{self.resource_id:016X}]"):
            raise ValidationError("External URL must start with the matching resource ID")


@dataclass(frozen=True)
class OwnedResourceRef:
    """Forward reference resolved against project-owned definitions at build time."""
    key: str
    kind: str = "other"

    def __post_init__(self):
        if not self.key:
            raise ValidationError("Owned reference needs a stable resource key")


@dataclass(frozen=True)
class Expr:
    data_type: T
    function: str | None = None
    arguments: tuple["Expr", ...] = ()
    value: Any = None

    def __bool__(self):
        raise TypeError("This is a game expression, not a Python bool. Use .equals(), conditions.all/any, or actions.when().")

    def equals(self, other) -> "Expr":
        """Build an integer/boolean game condition; never compare object identity."""
        if self.data_type not in (T.INTEGER, T.BOOLEAN):
            raise ValidationError("equals() currently supports integer and boolean expressions only")
        right = literal(other)
        if right.data_type != self.data_type:
            raise ValidationError("Equality operands must have the same data type")
        name = "conditions.integer_equals" if self.data_type == T.INTEGER else "conditions.boolean_equals"
        return call(name, self, Expr(T.COMPARISON, value=ComparisonOperator.EQUAL), right)


def literal(value) -> Expr:
    if isinstance(value, Expr):
        return value
    if isinstance(value, (ResourceRef, OwnedResourceRef)):
        return Expr(T.RESOURCE_LINK, value=value)
    if type(value) is bool:
        return Expr(T.BOOLEAN, value=value)
    if type(value) is int and -(2**31) <= value < 2**31:
        return Expr(T.INTEGER, value=value)
    if type(value) is str:
        return Expr(T.STRING, value=value)
    raise ValidationError(f"Unsupported literal type or integer range: {type(value).__name__}")


def call(name: str, *arguments) -> Expr:
    """Validate a named function signature before binary serialization."""
    if name not in FUNCTIONS:
        raise ValidationError(f"Unsupported function: {name}")
    spec = FUNCTIONS[name]
    values = tuple(literal(v) for v in arguments)
    if len(values) != len(spec.parameters):
        raise ValidationError(f"{name} expects {len(spec.parameters)} arguments, got {len(values)}")
    for parameter, value in zip(spec.parameters, values):
        if value.data_type != parameter.data_type:
            raise ValidationError(f"{name}.{parameter.name} expects {parameter.data_type.name}, got {value.data_type.name}")
        expected_kind = REFERENCE_ARGUMENT_KINDS.get(name, {}).get(parameter.name)
        if expected_kind and isinstance(value.value, (ResourceRef, OwnedResourceRef)) and value.value.kind not in ("other", expected_kind):
            raise ValidationError(f"{name}.{parameter.name} needs {expected_kind}, catalog declares {value.value.kind}")
    return Expr(spec.data_type, name, values)


def as_condition(value: Expr) -> Expr:
    if not isinstance(value, Expr):
        raise ValidationError("Expected a game expression, not a Python condition")
    if value.data_type == T.BOOLEAN:
        return value.equals(True)
    if value.data_type == T.CONDITION:
        return value
    raise ValidationError("Expected a boolean expression or condition")


def group(kind: ListKind, expressions=()) -> Expr:
    expected = {ListKind.EVENTS: T.EVENT, ListKind.CONDITIONS: T.CONDITION,
                ListKind.ACTIONS: T.ACTION, ListKind.SETUPS: T.ACTION}
    values = tuple(as_condition(v) for v in expressions) if kind == ListKind.CONDITIONS else tuple(expressions)
    if kind not in expected or any(not isinstance(v, Expr) or v.data_type != expected[kind] for v in values):
        raise ValidationError(f"Unexpected expression in {kind.name} list")
    return Expr(T.DATA_LIST, value=(kind, values))


def invoke(function_name: str, **arguments) -> Expr:
    """Call a documented named signature using explicit parameter names.

    This public escape hatch covers the wider verified registry without raw
    type/function IDs in source. Arguments are ordered by the registry, not by
    Python keyword insertion order.
    """
    if function_name not in FUNCTIONS:
        raise ValidationError(f"Unsupported function: {function_name}")
    names = [p.name for p in FUNCTIONS[function_name].parameters]
    if set(arguments) != set(names):
        raise ValidationError(f"{function_name} needs named arguments {names}, got {list(arguments)}")
    return call(function_name, *(arguments[key] for key in names))


def comparison(operator: ComparisonOperator) -> Expr:
    if not isinstance(operator, ComparisonOperator):
        raise ValidationError("Use a named ComparisonOperator")
    return Expr(T.COMPARISON, value=operator)


def localized_link(text) -> Expr:
    """A localized-link expression for native contextual notifications."""
    from .resources import LocalizedText
    if not isinstance(text, LocalizedText):
        raise ValidationError("localized_link needs LocalizedText, not a raw string")
    return call("text.localized_link", Expr(T.LOCALIZED_STRING_LINK_PRESET, value=text))
