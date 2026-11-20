"""Strict inverse recipes and template-free Python export for supported RPKs.

No resource IDs/names from a particular mod are hardcoded. Unknown fields and
noncanonical metadata fail rather than being hidden as entire record blobs.
"""
import ast
import hashlib
from importlib.resources import files as package_files
import json
from pathlib import Path
import re
from uuid import UUID

from ..constants import ClassId as C
from ..errors import ValidationError
from ..expressions import ResourceLink, ResourceHandle
from ..formats.binary import FieldTable, U32, U64, decode_string, encode_strings
from ..formats.rpk import ResourcePack, ResourceRecord
from ..project import TOOL_VERSION
from ..profiles import get_profile
from ..native_values import NATIVE_TYPES, native_description
from .python_export import _trigger_python_files, _constant, _call, _function, _statement
from .text_export import localized_description, localized_expression, localized_module

MAX_STATIC_PARAMETER_BYTES = 4096


def _table(raw, keys=None):
    result = FieldTable.read(raw).fields
    if keys is not None and set(result) != set(keys):
        raise ValidationError(f"Unsupported fields: expected {sorted(keys)}, found {sorted(result)}")
    return result


def _localized(raw):
    return localized_description(raw)


def _link(raw):
    row = _table(raw, {20, 22, 23})
    if len(row[22]) != 8:
        raise ValidationError("Invalid resource link ID width")
    link=ResourceLink(U64.unpack(row[22])[0],decode_string(row[23]),decode_string(row[20]))
    return dict(resource_id=f"{link.resource_id:016X}",name=link.name,url=link.url)


def _handles(raw):
    values = _table(_table(raw, {30})[30], {1})[1]
    rows = _table(values)
    if list(rows) != list(range(len(rows))):
        raise ValidationError("Noncanonical lightweight reference indices")
    result = []
    for value in rows.values():
        record = ResourceRecord.read(value)
        if record.class_id != 0x40004A or set(record.table.fields) != {20, 22} or len(record.table.fields[20]) != 8:
            raise ValidationError("Unknown lightweight link layout")
        handle=ResourceHandle(U64.unpack(record.table.fields[20])[0],decode_string(record.table.fields[22]))
        result.append(dict(resource_id=f"{handle.resource_id:016X}",name=handle.name))
    return result


def resource_specs(profile):
    schema = json.loads(package_files("aow4modkit").joinpath("resource_schemas", "strategic_2_3.json").read_text(encoding="utf-8"))
    if schema["profile"] != profile.key:
        raise ValidationError("Resource inverse recipes are unavailable for this profile")
    names = dict(strategic_army_spell="StrategicArmySpell", army_targeter="ArmyTargeter",
                 story_event="StoryEvent", research_skill="ResearchSkill",
                 spell_unlock_property="SpellUnlockProperty", texture_atlas_icon="TextureAtlasIcon")
    result = {}
    for key, spec in schema["resources"].items():
        result[int(spec["class_id"], 16)] = {**spec, "constructor": names[key]}
    result[int(C.SIDE_PROPERTY)] = dict(constructor="SideProperty", classes=[
        dict(class_id=f"{int(C.SIDE_PROPERTY_BASE):08X}", fields=[])])
    return result


def _validate_envelope(pack, profile):
    """The public constructor currently supports one canonical store/group."""
    name = decode_string(pack.table.fields[22])
    if len(set(pack.dependencies)) != len(pack.dependencies) or any(not re.fullmatch(r"[A-Z0-9_-]+\.(RPK|MO|CLB)",item) for item in pack.dependencies):
        raise ValidationError("Dependency list is not representable by the explicit RPK context")
    expected = ResourcePack.create(name, [], pack.dependencies, profile=profile)
    expected.table.fields[30] = encode_strings(pack.dependencies)
    offset = profile.rpk_length_offset
    if pack.prefix[:offset]+pack.prefix[offset+4:] != expected.prefix[:offset]+expected.prefix[offset+4:]:
        raise ValidationError("RPK header is not representable by the selected constructor profile")
    if {k:v for k,v in pack.table.fields.items() if k != 13} != {k:v for k,v in expected.table.fields.items() if k != 13}:
        raise ValidationError("RPK metadata differs from supported profile defaults")
    stores = list(pack.stores()); standard = next(expected.stores())[1]
    if len(stores) != 1 or stores[0][0] != 0:
        raise ValidationError("Template-free export currently requires store 0 only")
    store = stores[0][1]
    if store.prefix != standard.prefix or {k:v for k,v in store.manager.fields.items() if k != 21} != {k:v for k,v in standard.manager.fields.items() if k != 21}:
        raise ValidationError("Unsupported content-store metadata")
    groups = _table(store.manager.fields[21], {1})
    records = _table(groups[1])
    if list(records) != list(range(len(records))):
        raise ValidationError("Template-free export needs consecutive resource indices")
    for index, raw in records.items():
        record = ResourceRecord.read(raw)
        if not record.name:
            raise ValidationError("Named public resource recipes cannot reproduce an empty resource name")
        native = ResourceRecord.create(record.class_id, record.resource_id, record.name, index, {})
        metadata = {k:v for k,v in record.table.fields.items() if k < 0x10000 and not (record.class_id==C.TAG_BOOK and k==0)}
        if metadata != native.table.fields:
            raise ValidationError(f"Unsupported resource metadata for {record.resource_id:016X}")
    return name


def decode_resource_definitions(decoded):
    """Return readable inverse-recipe data; never whole-resource binary blobs."""
    profile = get_profile(decoded.profile)
    pack = ResourcePack.read(decoded._input_bytes, profile=profile)
    name = _validate_envelope(pack, profile)
    specs = resource_specs(profile)
    from .ascension_export import ASCENSION_CLASSES, tag_books, decode_ascension
    books = tag_books(pack)
    scripts = {(s.resource_id, s.role):s for s in decoded.scripts}
    definitions, preserved = [], []
    for _, _, index, record in pack.records():
        uid = f"{record.resource_id:016X}"
        identity = dict(key="resource_"+uid.lower(), name=record.name, resource_id=uid, index=index)
        if record.class_id == C.TRIGGER:
            definitions.append({**identity, "constructor":"Trigger", "script":scripts[(uid,"global")].path})
            continue
        if record.class_id in ASCENSION_CLASSES:
            try:
                recipe=decode_ascension(record,pack,profile,books)
            except (KeyError,IndexError) as exc:
                raise ValidationError(f'Missing ascension recipe fields in resource {uid}') from exc
            definitions.append({**identity,**recipe})
            continue
        spec = specs.get(record.class_id)
        if spec is None:
            raise ValidationError(f"No inverse resource recipe for class {record.class_id:08X} ({uid})")
        classes = {int(c["class_id"],16) for c in spec["classes"]}
        if {k for k in record.table.fields if k >= 0x10000} != classes:
            raise ValidationError(f"Unsupported class hierarchy in resource {uid}")
        parameters = {}
        for cls in spec["classes"]:
            values = record.class_fields(int(cls["class_id"],16)).fields
            if set(values) != {item["field"] for item in cls["fields"]}:
                raise ValidationError(f"Unknown or missing fields in resource {uid}, class {cls['class_id']}")
            for item in cls["fields"]:
                raw, codec = values[item["field"]], item["codec"]
                if codec == "link":
                    value = dict(link=_link(raw))
                elif codec == "links":
                    value = dict(handles=_handles(raw))
                elif codec == "localized":
                    value = dict(text=_localized(raw))
                elif codec == "bool":
                    if raw not in (b"\x00",b"\x01"):
                        raise ValidationError("Recipe boolean is not a single native 0/1 byte")
                    value = bool(raw[0])
                elif codec == "u32":
                    if len(raw) != 4:
                        raise ValidationError("Recipe integer must occupy four bytes")
                    value = U32.unpack(raw)[0]
                elif codec == "preserved":
                    if item.get("native_type"):
                        value = native_description(NATIVE_TYPES[item["native_type"]].decode(raw))
                    elif len(raw) > MAX_STATIC_PARAMETER_BYTES:
                        raise ValidationError("Static parameter exceeds bounded preservation allowance")
                    else:
                        key = f"{uid}_{item['name']}"
                        value = dict(preserved=key)
                        preserved.append(dict(key=key, hex=raw.hex(), size=len(raw),
                            description=f"Static {item['name']} field of resource {uid}; executable trigger fields are exported separately."))
                elif codec == "script":
                    value = dict(script=scripts[(uid,"initialization")].path)
                elif codec == "choices":
                    wrapper = _table(raw, {0,1})
                    if len(wrapper[0]) != 1:
                        raise ValidationError("Choice next-free ID must be one byte")
                    entries = _table(_table(wrapper[1],{1})[1])
                    if list(entries) != list(range(len(entries))):
                        raise ValidationError("Recipe cannot reproduce noncanonical choice array indices")
                    choices = []
                    for choice_index, blob in entries.items():
                        row = ResourceRecord.read(blob)
                        f = row.table.fields
                        if row.class_id != C.STORY_EVENT_CHOICE or set(f) != {0,2,3,4,5,6} or len(f[0]) != 1 or len(f[4]) != 4:
                            raise ValidationError("Unsupported dialog choice wrapper")
                        choices.append(dict(list_id=f[0][0], category=_link(f[3]), text=_localized(f[5]),
                            visibility_mode=U32.unpack(f[4])[0],
                            action=scripts[(uid,f"choice[{choice_index}].action")].path,
                            visibility=scripts[(uid,f"choice[{choice_index}].visibility")].path))
                    if wrapper[0][0] != max((c["list_id"] for c in choices),default=-1)+1:
                        raise ValidationError("Choice next-free ID cannot be reproduced by DialogChoice")
                    value = dict(choices=choices)
                else:
                    raise ValidationError(f"No inverse field codec for {codec}")
                parameters[item["name"]] = value
        definitions.append({**identity,"constructor":spec["constructor"],"parameters":parameters})
    return dict(name=name,profile=decoded.profile,dependencies=pack.dependencies,definitions=definitions,
                preserved=preserved)


def _parameter_ast(value):
    if isinstance(value,list):
        return ast.Tuple([_parameter_ast(item) for item in value],ast.Load())
    if not isinstance(value,dict):
        return _constant(value)
    if "native_type" in value:
        return _call(value["native_type"],**{k:_parameter_ast(v) for k,v in value["arguments"].items()})
    if "uuid" in value:
        return _call('UUID',_constant(value['uuid']))
    if "tag_definition" in value:
        row=value['tag_definition']
        return _call('TagDefinition',_constant(row['name']),_call('UUID',_constant(row['guid'])))
    if "tag_ref" in value:
        row=value['tag_ref']
        return _call('TagRef',book=_call('OwnedResourceRef',_constant(row['book']),_constant('tag_book')),
            path=_constant(row['path']),guid=_call('UUID',_constant(row['guid'])))
    if "link" in value:
        row=value["link"]
        return _call("ResourceLink",_constant(int(row["resource_id"],16)),_constant(row["name"]),_constant(row["url"]))
    if "handles" in value:
        return ast.Tuple([_call("ResourceHandle",_constant(int(row["resource_id"],16)),_constant(row["name"])) for row in value["handles"]],ast.Load())
    if "text" in value:
        row=value["text"]
        if isinstance(row,str):
            return ast.Subscript(ast.Name("resource_texts",ast.Load()),_constant(row),ast.Load())
        return localized_expression(row)
    if "preserved" in value:
        return ast.Subscript(ast.Name("preserved",ast.Load()),_constant(value["preserved"]),ast.Load())
    if "script" in value:
        return ast.Subscript(ast.Name("scripts",ast.Load()),_constant(value["script"]),ast.Load())
    if "choices" in value:
        result=[]
        for row in value["choices"]:
            result.append(_call("DialogChoice",list_id=_constant(row["list_id"]),
                category=_parameter_ast(dict(link=row["category"])),text=_parameter_ast(dict(text=row["text"])),
                action=_parameter_ast(dict(script=row["action"])),visibility=_parameter_ast(dict(script=row["visibility"])),
                visibility_mode=_constant(row["visibility_mode"])))
        return ast.Tuple(result,ast.Load())
    raise ValidationError("Unsupported inverse recipe parameter")


def _resource_source(definition):
    if definition["constructor"] == "Trigger":
        expression=_parameter_ast(dict(script=definition["script"]))
    else:
        kwargs=dict(key=_constant(definition["key"]),name=_constant(definition["name"]),
                    resource_id=_constant(int(definition["resource_id"],16)))
        if 'arguments' in definition:
            kwargs.update({key:_parameter_ast(value) for key,value in definition['arguments'].items()})
        elif definition["constructor"] != "SideProperty":
            values=definition["parameters"]
            kwargs["parameters"]=ast.Dict([_constant(k) for k in values],[_parameter_ast(v) for v in values.values()])
        expression=_call(definition["constructor"],**kwargs)
    imports=("SideProperty","StrategicArmySpell","ArmyTargeter","StoryEvent","ResearchSkill",
             "SpellUnlockProperty","TextureAtlasIcon","DialogChoice","ResourceLink","ResourceHandle","LocalizedText",
             "TextContext","TextContextStyle","TextSubstitution", "TagBook","TagDefinition","TagRef",
             "OwnedResourceRef","HiddenArtifactMarker","AscensionTrait","HeroSkill", *NATIVE_TYPES)
    used={node.func.id for node in ast.walk(expression) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name)}
    imports=tuple(name for name in imports if name in used)
    statements=[ast.ImportFrom("aow4modkit",[ast.alias(name) for name in imports],0)] if imports else []
    if 'UUID' in used:statements.insert(0,ast.ImportFrom('uuid',[ast.alias('UUID')],0))
    module=ast.Module(statements+[
        _function("build_resource",["scripts","preserved","resource_texts"],[ast.Return(expression)])],[])
    ast.fix_missing_locations(module)
    source="\n\n".join(_statement(stmt) for stmt in module.body)+"\n"
    compile(source,"resource.py","exec")
    return source


def export_pack_python(decoded, output, *, mod_id):
    """Export a complete supported RPK with no input/template binary file."""
    if mod_id is None:
        raise ValidationError("Template-free export requires an explicit original project UUID")
    try:
        identity=str(UUID(str(mod_id)))
    except ValueError as exc:
        raise ValidationError("Invalid original mod UUID") from exc
    description=decode_resource_definitions(decoded)
    buffers,bindings,_=_trigger_python_files(decoded,mod_id=identity,allow_empty=True)
    for name in ("input.rpk","rebuild.py","README.md"):
        buffers.pop(name)
    resource_texts={}
    text_keys={}
    def intern_texts(value):
        if isinstance(value,dict):
            for key,item in list(value.items()):
                if key == "text" and isinstance(item,dict) and "style" in item:
                    signature=json.dumps(item,sort_keys=True)
                    if signature not in text_keys:
                        identifier=f"text_{len(text_keys)+1:03d}"
                        text_keys[signature]=identifier;resource_texts[identifier]=item
                    value[key]=text_keys[signature]
                else:
                    intern_texts(item)
        elif isinstance(value,list):
            for item in value:intern_texts(item)
    intern_texts(description["definitions"])
    buffers["resource-texts.json"]=(json.dumps(resource_texts,indent=2)+"\n").encode()
    buffers["resource_texts.py"]=localized_module(resource_texts)
    modules=[]
    for definition in description["definitions"]:
        filename=f"resources/{definition['index']+1:03d}_{definition['resource_id']}.py"
        buffers[filename]=_resource_source(definition).encode("utf-8")
        modules.append(filename)
    preserved={row["key"]:{k:v for k,v in row.items() if k != "key"} for row in description["preserved"]}
    if preserved:
        buffers["preserved-parameters.json"]=(json.dumps(preserved,indent=2)+"\n").encode()
    context=dict(name=description["name"],profile=description["profile"],mod_id=identity,dependencies=description["dependencies"])
    buffers["pack-context.json"]=(json.dumps(context,indent=2)+"\n").encode()
    source = '''"""Complete RPK construction through public API. No input RPK is read."""
import json
from pathlib import Path
import runpy
from aow4modkit import ResourcePackProject, PreservedParameter, LocalizedText, get_profile

SOURCE = Path(__file__).resolve().parent
RESOURCE_MODULES = [
'''
    source += "".join(f"    {filename!r},\n" for filename in modules)
    source += ''']


def build_pack():
    context = json.loads((SOURCE / "pack-context.json").read_text(encoding="utf-8"))
    data = json.loads((SOURCE / "preserved-parameters.json").read_text(encoding="utf-8"))
    preserved = {
        key: PreservedParameter(bytes.fromhex(row["hex"]), row["description"])
        for key, row in data.items()
    }
    resource_texts = runpy.run_path(str(SOURCE / "resource_texts.py"))["TEXTS"]
    scripts = runpy.run_path(str(SOURCE / "triggers.py"))["build_triggers"]()
    definitions = []
    for filename in RESOURCE_MODULES:
        build_resource = runpy.run_path(str(SOURCE / filename))["build_resource"]
        definitions.append(build_resource(scripts, preserved, resource_texts))
    return ResourcePackProject(
        name=context["name"], mod_id=context["mod_id"],
        dependencies=tuple(context["dependencies"]), definitions=tuple(definitions),
        profile=get_profile(context["profile"]),
    )
'''
    if not preserved:
        start = source.index('    data = json.loads((SOURCE / "preserved-parameters.json")')
        end = source.index('    resource_texts = ',start)
        source = source[:start] + '    preserved = {}  # No opaque static values in this export.\n' + source[end:]
        source = source.replace('ResourcePackProject, PreservedParameter, LocalizedText','ResourcePackProject, LocalizedText')
    compile(source,"resources.py","exec")
    buffers["resources.py"]=source.encode()
    buffers["build.py"]=b'''"""Explicit trusted Python build; no binary template or automatic publication."""
import argparse,json
from pathlib import Path
from aow4modkit.analysis import build_pack_export

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--reference",type=Path,help="Optional read-only comparison after construction")
    parser.add_argument("--allow-changes",action="store_true")
    args=parser.parse_args()
    print(json.dumps(build_pack_export(Path(__file__).resolve().parent,args.output,reference=args.reference,allow_changes=args.allow_changes),indent=2))
'''
    buffers["README.md"]=("# Template-free RPK Python export\n\n"
        "Run: python build.py --output rebuilt/Example.rpk\n\n"
        "resources.py constructs every resource using public ModKit recipes.\n"
        "Scripts are in scripts/; named resource definitions are in resources/.\n"
        "resource_texts.py and localized_texts.py use LocalizedText, TextContext and\n"
        "TextSubstitution; the corresponding JSON files are readable metadata snapshots.\n"
        "There is no input.rpk, whole-record blob or template dependency.\n"
        "Supported static structures use named Python data constructors. Native numeric fields\n"
        "retain neutral names when their gameplay/rendering meaning is unverified.\n"
        "If any legacy opaque static values remain, they are listed in preserved-parameters.json.\n"
        "Pack/record defaults come from the supported SDK profile. Unsupported fields fail export.\n"
        "All IDs, choice IDs, original formatter contexts and dependency order are retained.\n"
        "External MO/CLB/image assets are references, not copied into this RPK-only export.\n"
        "An optional --reference ORIGINAL.rpk compares after construction; it is not required to build.\n"
        "Building explicitly executes trusted generated Python. No installation/publication occurs.\n").encode()
    manifest=dict(tool="AoW4 ModKit full RPK Python export",tool_version=TOOL_VERSION,
        profile=decoded.profile,input_sha256=decoded.source_sha256,mod_id=identity,
        resource_count=len(description["definitions"]),script_count=len(decoded.scripts),
        binary_template_required=False,preserved_static_parameters=len(preserved),
        preserved_static_bytes=sum(row["size"] for row in preserved.values()),
        typed_resource_text_contexts=len(resource_texts),
        typed_notification_text_contexts=len(json.loads(buffers["localized-links.json"])),
        equivalence_status="not yet independently compared",
        files={name:hashlib.sha256(data).hexdigest() for name,data in buffers.items()})
    buffers["pack-export-manifest.json"]=(json.dumps(manifest,indent=2)+"\n").encode()
    output=Path(output).absolute()
    if output.exists() and any(output.iterdir()):
        raise ValidationError("Full RPK export needs a new or empty directory")
    if output.is_symlink() or any(not (output/name).resolve().is_relative_to(output.resolve()) for name in buffers):
        raise ValidationError("RPK export path escapes its directory")
    output.mkdir(parents=True,exist_ok=True)
    for name,data in buffers.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return manifest
