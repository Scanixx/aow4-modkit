"""Strict trigger-only Python export through public ModKit authoring types.

Generated source is parsed but never executed during export. Unknown executable
data, unsupported state and unrepresentable slots fail before files are written.
"""
import ast
from collections import Counter
import hashlib
import json
import keyword
from pathlib import Path
import re
from uuid import UUID

from ..constants import ClassId as C, ComparisonOperator
from ..errors import ValidationError
from ..expressions import ResourceLink
from ..formats.binary import FieldTable
from ..project import TOOL_VERSION
from .report import walk_nodes
from .text_export import localized_description, localized_module


def _row_keys(raw):
    outer = FieldTable.read(raw)
    if not outer.fields:
        return []
    groups = FieldTable.read(outer.fields[0])
    return list(FieldTable.read(groups.fields[1]).fields)


def validate_trigger_export(pack):
    """Reject anything the current public compiler cannot reproduce exactly.

    Exact means script meaning and all nonscript values, excluding approved
    table framing and generated identity differences. It is not byte identity.
    """
    if not pack.scripts:
        raise ValidationError("No registered trigger scripts to export")
    if pack.diagnostics:
        first = pack.diagnostics[0]
        raise ValidationError(f"Strict trigger export blocked: {first.code} at {first.path}: {first.message}")
    for script in pack.scripts:
        if script.enabled is not True or script.active is not True:
            raise ValidationError(f"Unsupported disabled/inactive script at {script.path}")
        if script.context != (1 if script.role == "global" else 2):
            raise ValidationError(f"Unsupported context at {script.path}")
        if script.role == "global" and not script.phases["events"].children:
            raise ValidationError(f"Public Trigger requires an event at {script.path}")
        for phase, root in script.phases.items():
            pending = [(root, 0, phase == "setups", None)]
            while pending:
                node, slot, setup, parent = pending.pop()
                if node.enabled is not True or node.kind == "unknown" or node.unknown_fields or node.auxiliary_children:
                    raise ValidationError(f"Unsupported node state at {node.path}")
                if node.slot != slot:
                    raise ValidationError(f"Noncanonical slot at {node.path}: expected {slot}, found {node.slot}")
                if node.kind == "list":
                    if setup and node.list_kind == 3:
                        raise ValidationError(f"Action list inside setup phase cannot be reproduced at {node.path}")
                    keys = _row_keys(pack.source_bytes(node.fields[20].span))
                    if keys != list(range(len(node.children))):
                        raise ValidationError(f"Noncanonical list row indices at {node.path}")
                    pending.extend((child, 0, setup, node) for child in reversed(node.children))
                elif node.kind == "call":
                    if not node.function_name:
                        raise ValidationError(f"Unknown function at {node.path}")
                    if node.data_type in (2, 3) and (node.data_type == 2) != setup:
                        raise ValidationError(f"Action/setup context cannot be reproduced at {node.path}")
                    if setup and node.data_type == 2 and not 0 <= node.function_id <= 12:
                        raise ValidationError(f"Unsupported setup counterpart at {node.path}")
                    keys = _row_keys(pack.source_bytes(node.fields[2].span))
                    if keys != list(range(len(node.children))):
                        raise ValidationError(f"Noncanonical argument row indices at {node.path}")
                    pending.extend((child, index, setup, node) for index, child in reversed(list(enumerate(node.children, 1))))
                elif node.kind == "preset":
                    if node.data_type in (9, 11, 18, 26, 133):
                        expected = {9: "literal.integer", 11: "literal.boolean", 18: "literal.string",
                                    26: "variables.name", 133: "text.localized_link"}[node.data_type]
                        if parent is None or parent.function_name != expected:
                            raise ValidationError(f"Unsupported stand-alone preset at {node.path}")
                    if node.data_type == 7:
                        try:
                            ComparisonOperator(node.value)
                        except ValueError as exc:
                            raise ValidationError(f"Unnamed comparison operator at {node.path}") from exc
                    if node.data_type == 31:
                        value = node.value
                        ResourceLink(int(value["resource_id"], 16), value["name"], value["url"])
    return True


def _slug(value):
    text = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")[:60] or "value"
    return "item_"+text if text[0].isdigit() or keyword.iskeyword(text) else text


def _call(function_name, *args, **kwargs):
    return ast.Call(ast.Name(function_name, ast.Load()), list(args), [ast.keyword(key, value) for key, value in kwargs.items()])


def _constant(value):
    return ast.Constant(value)


def _subscript(name, key):
    return ast.Subscript(ast.Name(name, ast.Load()), _constant(key), ast.Load())


def _expression(expr, indent=0, prefix=0):
    flat = ast.unparse(expr)
    if len(flat)+indent+prefix <= 100:
        return flat
    padding = " " * indent
    if isinstance(expr, ast.Call):
        parts = [(None, arg) for arg in expr.args] + [(kw.arg, kw.value) for kw in expr.keywords]
        lines = [ast.unparse(expr.func)+"("]
        for name, value in parts:
            key = (name+"=") if name is not None else ""
            lines.append(padding+"    "+key+_expression(value, indent+4, len(key))+",")
        return "\n".join(lines+[padding+")"])
    if isinstance(expr, (ast.List, ast.Tuple)):
        opening, closing = ("[", "]") if isinstance(expr, ast.List) else ("(", ")")
        return opening+"\n"+"\n".join(padding+"    "+_expression(value, indent+4)+"," for value in expr.elts)+"\n"+padding+closing
    if isinstance(expr, ast.Dict):
        return "{\n"+"\n".join(padding+"    "+_expression(key,indent+4)+": "+
            _expression(value,indent+4)+"," for key,value in zip(expr.keys,expr.values))+"\n"+padding+"}"
    return flat


def _statement(stmt, indent=0):
    padding = " "*indent
    if isinstance(stmt, ast.FunctionDef):
        params = ", ".join(arg.arg for arg in stmt.args.args)
        return padding+f"def {stmt.name}({params}):\n"+"\n".join(_statement(s, indent+4) for s in stmt.body)+"\n"
    if isinstance(stmt, ast.Assign):
        prefix = ast.unparse(stmt.targets[0])+" = "
        return padding+prefix+_expression(stmt.value, indent, len(prefix))
    if isinstance(stmt, ast.Return):
        return padding+"return "+_expression(stmt.value, indent, 7)
    return padding+ast.unparse(stmt)


def _function(name, arguments, body):
    return ast.FunctionDef(name, ast.arguments(posonlyargs=[], args=[ast.arg(a) for a in arguments],
                           kwonlyargs=[], kw_defaults=[], defaults=[]), body, [], None)


class _ScriptEmitter:
    def __init__(self, script, links, texts):
        self.script, self.links, self.texts = script, links, texts
        self.statements, self.memo, self.fingerprints, self.names = [], {}, {}, Counter()
        self.counts = Counter()
        for root in script.phases.values():
            for node in walk_nodes(root):
                self.counts[self.fingerprint(node)] += 1

    def fingerprint(self, node):
        if id(node) not in self.fingerprints:
            data = [node.class_id, node.data_type, node.function_id, node.list_kind, node.value,
                    [self.fingerprint(child) for child in node.children]]
            self.fingerprints[id(node)] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        return self.fingerprints[id(node)]

    def name(self, stem):
        stem = _slug(stem)
        self.names[stem] += 1
        return stem if self.names[stem] == 1 else stem+"_"+str(self.names[stem])

    @staticmethod
    def suffix(node):
        for value in walk_nodes(node):
            if value.function_name == "variables.name" and value.children:
                return "_"+_slug(str(value.children[0].value))[:32]
        return ""

    def expression(self, node):
        key = self.fingerprint(node)
        if key in self.memo:
            return self.memo[key]
        if node.kind == "preset":
            if node.data_type == 31:
                value = node.value
                link_key = self.links[(value["resource_id"], value["name"], value["url"])]
                return _subscript("references", link_key)
            if node.data_type == 7:
                return _call("comparison", ast.Attribute(ast.Name("ComparisonOperator", ast.Load()), ComparisonOperator(node.value).name, ast.Load()))
            raise ValidationError(f"Preset requires its native getter at {node.path}")
        if node.kind == "list":
            label = {0: "EVENTS", 1: "CONDITIONS", 2: "SETUPS", 3: "ACTIONS"}[node.list_kind]
            return _call("sequence", ast.Attribute(ast.Name("ListKind", ast.Load()), label, ast.Load()),
                         ast.List([self.expression(child) for child in node.children], ast.Load()))
        if node.function_name.startswith("literal."):
            return _constant(node.children[0].value)
        if node.function_name == "variables.name":
            expr = _call("variables.name", _constant(node.children[0].value))
            expr.func = ast.Attribute(ast.Name("variables", ast.Load()), "name", ast.Load())
        elif node.function_name == "text.localized_link":
            text = node.children[0].value
            expr = _call("localized_link", _subscript("texts", self.texts[(text["key"], text["original_hex"])]))
        else:
            arguments = []
            for child in node.children:
                if not child.parameter_name or not child.parameter_name.isidentifier() or keyword.iskeyword(child.parameter_name):
                    raise ValidationError(f"Unrepresentable named parameter at {child.path}")
                arguments.append(ast.keyword(child.parameter_name, self.expression(child)))
            expr = ast.Call(ast.Name("invoke", ast.Load()), [_constant(node.function_name)], arguments)
        if node.function_name == "actions.when":
            check = node.children[0].children
            condition = check[0] if check else node
            left = condition.children[0] if condition.children else condition
            stem = "branch_when_"+(left.function_name or "conditions_hold").replace(".", "_")+self.suffix(left)
            name = self.name(stem)
            self.statements.append(_function(name, [], [ast.Expr(_constant(
                f"Generated native branch; original bytes {node.span[0]}..{node.span[1]}.")), ast.Return(expr)]))
            result = _call(name)
            self.memo[key] = result
            return result
        # Share immutable expression definitions, never evaluated game values.
        # Deep unique expressions are also lifted to avoid Python parser limits.
        complexity = sum(1 for _ in ast.walk(expr))
        if self.counts[key] > 1 or complexity > 120:
            name = self.name("value_"+node.function_name.replace(".", "_")+self.suffix(node))
            self.statements.append(ast.Assign([ast.Name(name, ast.Store())], expr))
            result = ast.Name(name, ast.Load())
            self.memo[key] = result
            return result
        return expr

    def source(self):
        phases = {name: ast.List([self.expression(child) for child in root.children], ast.Load())
                  for name, root in self.script.phases.items()}
        kwargs = dict(key=_constant("export."+self.script.resource_id.lower()+"."+self.script.role), events=phases["events"],
                      conditions=phases["conditions"], actions=phases["actions"], setups=phases["setups"],
                      once=_constant(self.script.once), context=_constant(self.script.context), comment=_constant(self.script.comment))
        if self.script.role == "global":
            kwargs.update(resource_id=_constant(int(self.script.resource_id, 16)), name=_constant(self.script.resource_name))
        constructor = "Trigger" if self.script.role == "global" else "Script"
        body = [ast.Expr(_constant("Expression variables describe future native reads; they do not cache live game values.")),
                *self.statements, ast.Return(_call(constructor, **kwargs))]
        module = ast.Module([
            ast.Expr(_constant(f"Generated public-API source: {self.script.resource_name}; {self.script.role}.\n"
                              "Equivalent compiled representation, not recovered original author source.")),
            ast.ImportFrom("aow4modkit", [ast.alias(name) for name in (
                "Trigger", "Script", "invoke", "sequence", "ListKind", "comparison", "ComparisonOperator", "variables", "localized_link")], 0),
            _function("build_script", ["references", "texts"], body)], [])
        ast.fix_missing_locations(module)
        source = "\n\n".join(_statement(stmt) for stmt in module.body)+"\n"
        compile(source, "generated_trigger.py", "exec")  # Syntax only, not execution.
        return source


def _trigger_python_files(pack, *, mod_id=None, allow_empty=False):
    """Create source buffers without writing or executing generated Python."""
    if pack.scripts or not allow_empty:
        validate_trigger_export(pack)
    elif pack.diagnostics:
        raise ValidationError("Cannot export an RPK with unresolved diagnostics")
    if mod_id is not None:
        try:
            mod_id = str(UUID(str(mod_id)))
        except ValueError as exc:
            raise ValidationError("Invalid explicit mod UUID") from exc
    links, texts, link_rows, text_rows = {}, {}, {}, {}
    for script in pack.scripts:
        for root in script.phases.values():
            for node in walk_nodes(root):
                if node.kind == "preset" and node.data_type == 31:
                    value = node.value
                    signature = (value["resource_id"], value["name"], value["url"])
                    if signature not in links:
                        key = f"{_slug(value['name'])}_{len(links)+1:03d}"
                        links[signature] = key
                        link_rows[key] = {k: value[k] for k in ("resource_id", "name", "url")}
                if node.kind == "preset" and node.data_type == 133:
                    value = node.value; signature = (value["key"], value["original_hex"])
                    if signature not in texts:
                        key = f"{_slug(value['key'])}_{len(texts)+1:03d}"
                        texts[signature] = key
                        text_rows[key] = localized_description(bytes.fromhex(value["original_hex"]))
    files, bindings = {}, []
    for index, script in enumerate(pack.scripts, 1):
        filename = f"scripts/{index:03d}_{script.resource_id}_{_slug(script.role)}.py"
        source = _ScriptEmitter(script, links, texts).source()
        files[filename] = source.encode("utf-8")
        bindings.append(dict(path=script.path, resource_id=script.resource_id, role=script.role,
                             choice_id=script.choice["list_id"] if script.choice else None, file=filename))
    files["resource-links.json"] = (json.dumps(link_rows, indent=2, ensure_ascii=False)+"\n").encode("utf-8")
    files["localized-links.json"] = (json.dumps(text_rows, indent=2, ensure_ascii=False)+"\n").encode("utf-8")
    files["localized_texts.py"] = localized_module(text_rows)
    files["script-bindings.json"] = (json.dumps(bindings, indent=2)+"\n").encode()
    # All input-derived text below is emitted as Python constants, not code.
    builder = '''"""Build exported Trigger/Script objects. Executes trusted Python only when called."""
import json
from pathlib import Path
import runpy
from aow4modkit import ResourceLink, LocalizedText

SOURCE = Path(__file__).resolve().parent

def build_triggers():
    links = json.loads((SOURCE / "resource-links.json").read_text(encoding="utf-8"))
    references = {key: ResourceLink(int(row["resource_id"], 16), row["name"], row["url"])
                  for key, row in links.items()}
    texts = runpy.run_path(str(SOURCE / "localized_texts.py"))["TEXTS"]
    definitions = {}
'''
    for binding in bindings:
        builder += f"    definitions[{binding['path']!r}] = runpy.run_path(str(SOURCE / {binding['file']!r}))['build_script'](references, texts)\n"
    builder += "    return definitions\n"
    compile(builder, "triggers.py", "exec")
    files["triggers.py"] = builder.encode("utf-8")
    files["rebuild.py"] = b'''"""Explicitly rebuild trusted exported Python; no installation or publishing."""
import argparse
import json
from pathlib import Path
from aow4modkit.analysis import rebuild_export

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mod-id", help="Original project UUID, if not supplied at export")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-changes", action="store_true", help="Permit intentional semantic differences")
    args = parser.parse_args()
    print(json.dumps(rebuild_export(Path(__file__).resolve().parent, args.output,
        mod_id=args.mod_id, allow_changes=args.allow_changes), indent=2))
'''
    files["input.rpk"] = pack._input_bytes
    files["README.md"] = ("# Strict trigger Python export\n\n"
        "This directory contains public-API Python for registered triggers only.\n"
        "Read scripts/ and edit native branches there; triggers.py loads their definitions.\n"
        "Shared expression objects are build-time definitions, not cached game values.\n\n"
        "localized_texts.py contains typed text layouts and formatter substitutions;\n"
        "localized-links.json is a readable metadata snapshot, not a binary context.\n\n"
        "The input.rpk template preserves nontrigger resources, choice IDs/text/categories,\n"
        "and other metadata. No executable script graph is hidden in the JSON files.\n"
        "The original mod UUID must be supplied at export or through --mod-id.\n\n"
        "Run explicitly with a compatible ModKit development version:\n\n"
        "    python rebuild.py --output rebuilt/Example.rpk\n\n"
        "Rebuilding executes trusted exported Python. Export itself does not execute it.\n"
        "Default rebuild requires normalized equivalence; --allow-changes enables intentional edits.\n"
        "Native script semantics are compared, not original author source or exact RPK bytes.\n"
        "Only generated identity bytes and known table framing may differ. No engine test is implied.\n"
        "Inspection cannot establish external resource pack/DLC origins. ResourceLink retains\n"
        "the serialized link without inventing them; a new full ModProject needs ResourceRef declarations.\n"
        "Use a fresh export directory to preserve edits; no files are installed or published.\n").encode()
    return files, bindings, mod_id


def export_trigger_python(pack, output, *, mod_id=None):
    """Write strict trigger-only source with an explicit nonscript template."""
    files, bindings, mod_id = _trigger_python_files(pack, mod_id=mod_id)
    manifest = dict(tool="AoW4 ModKit trigger Python export", tool_version=TOOL_VERSION,
                    scope="registered triggers only", input_sha256=pack.source_sha256, profile=pack.profile,
                    mod_id=mod_id, script_count=len(pack.scripts), node_count=pack.statistics["nodes"],
                    equivalence_status="not yet rebuilt", nontrigger_template_required=True,
                    files={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()})
    files["export-manifest.json"] = (json.dumps(manifest, indent=2)+"\n").encode()
    output = Path(output).absolute()
    if output.exists() and any(output.iterdir()):
        raise ValidationError("Python export requires a new or empty directory; existing source is never overwritten")
    if output.is_symlink() or any(not (output/name).resolve().is_relative_to(output.resolve()) for name in files):
        raise ValidationError("Python export path escapes its directory")
    output.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        target = output/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    return manifest
