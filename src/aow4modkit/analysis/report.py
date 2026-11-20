"""Readable, nonexecuting trigger outlines and owned analysis-directory output."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from ..constants import ComparisonOperator
from ..errors import ValidationError
from ..project import TOOL_VERSION
from .model import DecodedPack

KINDS = {0: "events", 1: "conditions", 2: "setups", 3: "actions"}


def walk_nodes(root):
    """Walk all decoded nodes in native order without evaluating expressions."""
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.children + node.auxiliary_children))


def _label(node):
    if node.kind == "list":
        return KINDS.get(node.list_kind, f"list_kind_{node.list_kind}")
    if node.kind == "call":
        name = node.function_name or f"UNKNOWN_FUNCTION[{node.data_type}:{node.function_id}]"
        return name + (" [native setup]" if node.data_type == 2 else "")
    if node.kind == "unknown":
        return f"UNKNOWN_NODE[class={node.class_id:08X}, type={node.data_type}]"
    if node.data_type == 31 and isinstance(node.value, dict):
        return "reference"
    if node.data_type == 133:
        return "localized_key"
    return "preset"


def _value(node):
    if node.data_type == 31 and isinstance(node.value, dict):
        return f"ref({node.value['resource_id']!r}, name={node.value['name']!r})"
    if node.data_type == 133 and isinstance(node.value, dict):
        return f"localized_key({node.value['key']!r})"
    if node.data_type == 7:
        try:
            return "ComparisonOperator." + ComparisonOperator(node.value).name
        except ValueError:
            return f"comparison_operator({node.value!r})"
    return repr(node.value)


def _prefix(node):
    flags = []
    if node.enabled is False:
        flags.append("DISABLED")
    elif node.enabled is None:
        flags.append("ENABLED_STATE_UNKNOWN")
    if node.unknown_fields:
        flags.append("EXTRA_FIELDS=" + ",".join(map(str, node.unknown_fields)))
    return ("[" + "; ".join(flags) + "] ") if flags else ""


def _inline(node, width=110):
    """Compact only complete known expressions; never reorder or evaluate them."""
    if node.kind == "unknown" or node.auxiliary_children or (node.kind == "call" and not node.function_name):
        return None
    if node.kind == "preset":
        value = _prefix(node) + _value(node)
    else:
        parts = []
        for child in node.children:
            rendered = _inline(child, width)
            if rendered is None:
                return None
            parameter = child.parameter_name or (f"slot_{child.slot}" if node.kind == "call" else None)
            parts.append((parameter + "=" if parameter else "") + rendered)
            if sum(map(len, parts)) > width:
                return None
        label = _label(node)
        if node.kind == "list":
            value = f"{label}[" + ", ".join(parts) + "]"
        elif node.function_name and node.function_name.startswith("literal.") and len(parts) == 1:
            # The literal getter remains explicit in JSON, but is ordinary text
            # in a readable expression. Keep any disabled-child marker visible.
            value = parts[0].removeprefix("value=")
        else:
            value = f"{label}(" + ", ".join(parts) + ")"
        value = _prefix(node) + value
    return value if len(value) <= width else None


def _outline(node, depth=0, parameter=None):
    indent = "  " * depth
    start = (parameter + " = ") if parameter else ""
    inline = _inline(node)
    if inline is not None:
        return [indent + start + inline]
    line = indent + start + _prefix(node) + _label(node)
    if node.kind == "preset":
        return [line + " " + _value(node)]
    lines = [line + f"  # bytes {node.span[0]}..{node.span[1]}"]
    if node.kind == "call" and node.function_name == "actions.when":
        # Registered slots retain names; no conversion to Python `if` with
        # different short-circuit/evaluation semantics is performed.
        branch_names = {"conditions": "CHECK", "then": "THEN", "otherwise": "OTHERWISE"}
    else:
        branch_names = {}
    for child in node.children:
        label = child.parameter_name
        if node.kind == "call" and label is None:
            label = f"slot_{child.slot}"
        lines += _outline(child, depth+1, branch_names.get(label, label))
    for child in node.auxiliary_children:
        lines += _outline(child, depth+1, "AUXILIARY_CHILD")
    return lines


def render_script(script):
    """Human outline, not executable Python or a promise of rebuild support."""
    lines = [f"Resource: {script.resource_name!r} [{script.resource_id}]",
             f"Role: {script.role}", f"Origin: {script.path}",
             f"Bytes: {script.span[0]}..{script.span[1]} (end exclusive)",
             f"Context={script.context}; once={script.once}; enabled={script.enabled}; active={script.active}",
             f"Serialized comment: {script.comment!r}"]
    if script.choice:
        choice = script.choice
        lines += [f"Choice: index={choice['index']}, list_id={choice['list_id']}, visibility_mode={choice['visibility_mode']}, next_free_id={choice['next_free_id']}",
                  f"Choice text key: {choice['text']['key']!r}",
                  f"Choice category: {choice['category']['name']!r}"]
    lines += ["", "ANALYSIS ONLY: named native expressions, not runnable Python.",
              "Disabled flags are displayed, not simulated. Guard order is retained.", ""]
    for name, root in script.phases.items():
        lines.append(name.upper())
        for child in root.children:
            lines += _outline(child, 1)
        if not root.children:
            lines.append("  (empty)")
        if root.enabled is not True or root.unknown_fields or root.auxiliary_children:
            lines.append("  ROOT METADATA: " + _prefix(root))
            for child in root.auxiliary_children:
                lines += _outline(child, 1, "AUXILIARY_CHILD")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_report(pack):
    """Describe measured coverage; do not imply complete resource decoding."""
    stats = pack.statistics
    lines = ["# RPK trigger analysis", "", f"Input: {pack.source_name!r}",
             f"SHA-256: `{pack.source_sha256}`", f"Profile: `{pack.profile}`", "",
             "This is a nonexecuting analysis of registered trigger locations. It is not a complete mod export.", "",
             f"- Resources inventoried: {stats['resources']}",
             f"- Resources with supported script locators: {stats['resources_with_script_locators']}",
             f"- Other resources (inventory only): {stats['resources_inventoried_only']}",
             f"- Scripts: {stats['scripts']}; nodes: {stats['nodes']}",
             f"- Unknown nodes/functions: {stats['unknown_nodes']}; disabled nodes: {stats['disabled_nodes']}",
             f"- Repeated serialized node identities: {stats['duplicate_node_identities']}",
             f"- Diagnostics: {stats['errors']} errors, {stats['warnings']} warnings", "",
             "Known fields retain exact byte ranges and hashes. Unknown data remains in the original input copy; it is never replaced or executed.",
             "Reference names come from serialized links; external pack/DLC origins and translated strings are not inferred.", "",
             "## Script index", ""]
    for index, script in enumerate(pack.scripts, 1):
        filename = f"scripts/{index:03d}-{script.resource_id}.txt"
        label = f"{index}. {script.resource_name!r}: {script.role}"
        lines.append(f"- [{label}]({filename})")
    lines += ["", "## Native function usage", ""]
    counts = Counter((node.data_type, node.function_id, node.function_name) for script in pack.scripts
                     for root in script.phases.values() for node in walk_nodes(root) if node.kind == "call")
    for (typ, fid, name), count in sorted(counts.items(), key=lambda row: (
            row[0][0] if row[0][0] is not None else -1, row[0][1] if row[0][1] is not None else -1)):
        lines.append(f"- `{name or 'UNKNOWN'}` (native `{typ}:{fid}`): {count}")
    lines += ["", "## Diagnostics", ""]
    for diagnostic in pack.diagnostics:
        lines.append(f"- **{diagnostic.severity}: {diagnostic.code}** at `{diagnostic.path}`: {diagnostic.message}")
    if not pack.diagnostics:
        lines.append("No diagnostics in decoded script locations. Other resource fields were not semantically certified.")
    lines += ["", "## Rebuild status", "", "Not attempted. This decoder does not generate a buildable project or execute extracted source."]
    return "\n".join(lines) + "\n"


def write_analysis(pack: DecodedPack, output):
    """Write an owned analysis folder, never the selected input or game files.

    Original RPK bytes are included so ranges/unknown fields are recoverable.
    Reports may contain input-author content and are not SDK release fixtures.
    """
    output = Path(output).absolute()
    if output.is_symlink():
        raise ValidationError("Analysis output must not be a symbolic link")
    marker = output / "analysis-manifest.json"
    if output.exists() and any(output.iterdir()):
        if marker.is_symlink() or not marker.is_file():
            raise ValidationError("Analysis output is nonempty and has no ownership manifest")
        try:
            prior = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationError("Cannot read existing analysis manifest") from exc
        if prior.get("tool") != "AoW4 ModKit trigger analysis" or prior.get("input_sha256") != pack.source_sha256:
            raise ValidationError("Analysis output belongs to another input or tool")
        for name, digest in prior.get("files", {}).items():
            target = output / name
            if not target.resolve().is_relative_to(output.resolve()) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValidationError("Existing analysis output has user changes or invalid paths; choose a fresh directory")
    files = {"decoded.json": (json.dumps(pack.to_dict(), indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
             "report.md": render_report(pack).encode("utf-8"), "input.rpk": pack._input_bytes}
    rendered = []
    for index, script in enumerate(pack.scripts, 1):
        text = render_script(script)
        files[f"scripts/{index:03d}-{script.resource_id}.txt"] = text.encode("utf-8")
        rendered.append(text)
    files["triggers.txt"] = ("\n" + "="*80 + "\n").join(rendered).encode("utf-8")
    manifest = dict(tool="AoW4 ModKit trigger analysis", tool_version=TOOL_VERSION, ir_version=pack.ir_version,
                    input_sha256=pack.source_sha256, analysis_only=True,
                    files={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()})
    files["analysis-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    if output.exists():
        existing = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
        if existing - set(files):
            raise ValidationError("Analysis output contains unrelated files; choose a fresh directory")
    for name in files:
        if not (output / name).resolve().is_relative_to(output.resolve()):
            raise ValidationError("Analysis output path escapes its directory")
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return output
