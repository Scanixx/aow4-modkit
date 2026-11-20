"""Versioned, inert trigger-analysis data. None of these objects executes code."""
from dataclasses import dataclass, field, fields, is_dataclass

IR_VERSION = 1


def plain(value):
    """Convert IR to JSON data, excluding the private original byte buffer."""
    if is_dataclass(value):
        return {item.name: plain(getattr(value, item.name)) for item in fields(value)
                if not item.name.startswith("_")}
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


@dataclass(frozen=True)
class DecodeLimits:
    max_input_bytes: int = 64 * 1024 * 1024
    max_parsed_bytes: int = 512 * 1024 * 1024
    max_nodes: int = 200_000
    max_fields: int = 1_000_000
    max_resources: int = 20_000
    max_depth: int = 128
    max_diagnostics: int = 20_000

    def __post_init__(self):
        if any(type(getattr(self, item.name)) is not int or getattr(self, item.name) <= 0
               for item in fields(self)):
            raise ValueError("Decode limits must be positive integers")
        if self.max_depth > 128:
            raise ValueError("Recursive trigger decoding supports a maximum depth of 128")


@dataclass
class Diagnostic:
    code: str
    severity: str
    path: str
    message: str
    span: tuple[int, int] | None = None


@dataclass
class FieldOrigin:
    span: tuple[int, int]
    size: int
    sha256: str


@dataclass
class Node:
    path: str
    span: tuple[int, int]
    class_id: int
    data_type: int | None
    slot: int | None
    enabled: bool | None
    kind: str
    fields: dict[int, FieldOrigin]
    function_id: int | None = None
    function_name: str | None = None
    aliases: tuple[str, ...] = ()
    list_kind: int | None = None
    parameter_name: str | None = None
    value: object = None
    identity: str | None = None
    parent_resource_id: str | None = None
    children: list["Node"] = field(default_factory=list)
    auxiliary_children: list["Node"] = field(default_factory=list)
    unknown_fields: tuple[int, ...] = ()


@dataclass
class Script:
    path: str
    span: tuple[int, int]
    resource_id: str
    resource_name: str
    role: str
    fields: dict[int, FieldOrigin]
    context: int | None
    once: bool | None
    enabled: bool | None
    active: bool | None
    comment: str | None
    phases: dict[str, Node]
    choice: dict | None = None


@dataclass
class DecodedPack:
    source_name: str
    source_sha256: str
    source_size: int
    profile: str
    dependencies: list[str]
    resources: list[dict]
    scripts: list[Script]
    diagnostics: list[Diagnostic]
    references: list[dict]
    statistics: dict
    ir_version: int = IR_VERSION
    analysis_only: bool = True
    _input_bytes: bytes = field(default=b"", repr=False)

    def to_dict(self):
        # Flatten the node graph. Nested JSON indentation otherwise dominates
        # large, deeply guarded scripts and repeats whole subtrees in consumers.
        result = {item.name: plain(getattr(self, item.name)) for item in fields(self)
                  if not item.name.startswith("_") and item.name != "scripts"}
        nodes, identities = [], {}
        pending = [root for script in self.scripts for root in script.phases.values()]
        pending.reverse()
        while pending:
            node = pending.pop()
            if id(node) in identities:
                continue
            identities[id(node)] = f"n{len(nodes)+1:06d}"
            nodes.append(node)
            pending.extend(reversed(node.children + node.auxiliary_children))
        result["node_representation"] = "flat-v1"
        result["nodes"] = []
        for node in nodes:
            value = {item.name: plain(getattr(node, item.name)) for item in fields(node)
                     if item.name not in ("children", "auxiliary_children")}
            value.update(node_id=identities[id(node)],
                         children=[identities[id(n)] for n in node.children],
                         auxiliary_children=[identities[id(n)] for n in node.auxiliary_children])
            result["nodes"].append(value)
        result["scripts"] = []
        for script in self.scripts:
            value = {item.name: plain(getattr(script, item.name)) for item in fields(script) if item.name != "phases"}
            value["phases"] = {name: identities[id(node)] for name, node in script.phases.items()}
            result["scripts"].append(value)
        return result

    def source_bytes(self, span):
        """Return the exact original bytes for an end-exclusive source range."""
        start, end = span
        if not 0 <= start <= end <= len(self._input_bytes):
            raise ValueError("Source range outside input")
        return self._input_bytes[start:end]
