"""Explicit template-free resource-pack builds and schema-aware comparison."""
import hashlib
import json
from pathlib import Path
import runpy

from ..errors import ValidationError
from ..pack_project import ResourcePackProject
from ..profiles import DEFAULT_PROFILE
from .reader import decode_pack, read_pack
from .resource_export import decode_resource_definitions
from .equivalence import normalized_script


def _normalized_recipe(value):
    """Keep values exact while ignoring only a named handle-directory choice."""
    if isinstance(value,list):
        return [_normalized_recipe(item) for item in value]
    if isinstance(value,dict):
        if value.get("native_type") == "ResourceHandleList":
            return {**value,"arguments":{key:_normalized_recipe(item)
                for key,item in value["arguments"].items() if key != "compact"}}
        return {key:_normalized_recipe(item) for key,item in value.items()}
    return value


def compare_resource_packs(before: bytes, after: bytes, *, profile=DEFAULT_PROFILE):
    """Compare all supported recipe fields, metadata and native script graphs."""
    a,b=decode_pack(before,profile=profile),decode_pack(after,profile=profile)
    old,new=decode_resource_definitions(a),decode_resource_definitions(b)
    old_scripts={(s.resource_id,s.role):s for s in a.scripts}
    new_scripts={(s.resource_id,s.role):s for s in b.scripts}
    scripts_equal=list(old_scripts)==list(new_scripts)
    differing_scripts=[]
    if scripts_equal:
        for key,script in old_scripts.items():
            if normalized_script(a,script) != normalized_script(b,new_scripts[key]):
                differing_scripts.append(dict(resource_id=key[0],role=key[1]))
    records_equal=_normalized_recipe(old)==_normalized_recipe(new)
    clear=not a.diagnostics and not b.diagnostics
    return dict(equivalent=records_equal and scripts_equal and not differing_scripts and clear,
        scope="All supported resource recipes, pack/store/record metadata and registered scripts",
        resources_compared=len(old["definitions"]),resource_fields_equal=records_equal,
        script_inventory_equal=scripts_equal,scripts_compared=len(old_scripts) if scripts_equal else 0,
        nodes_before=a.statistics["nodes"],nodes_after=b.statistics["nodes"],differing_scripts=differing_scripts,
        preserved_static_parameters=len(old["preserved"]),
        preserved_static_bytes=sum(row["size"] for row in old["preserved"]),
        ignored_differences=["Known field-table directory framing","Generated node identity bytes, with parent IDs compared","RPK payload length header"],
        input_diagnostics=len(a.diagnostics),rebuilt_diagnostics=len(b.diagnostics),runtime_tested=False)


def build_pack_export(directory,output,*,reference=None,allow_changes=False):
    """Explicitly execute trusted resource Python; no input/template is loaded.

    Optional reference is read only after construction, solely for comparison.
    Without it the build report makes no equivalence claim.
    """
    directory=Path(directory).resolve()
    manifest=json.loads((directory/"pack-export-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("tool") != "AoW4 ModKit full RPK Python export" or manifest.get("binary_template_required") is not False:
        raise ValidationError("Directory is not a template-free RPK Python export")
    project=runpy.run_path(str(directory/"resources.py"))["build_pack"]()
    if not isinstance(project,ResourcePackProject):
        raise ValidationError("build_pack must return public ResourcePackProject")
    data=project.build()
    if len(project.definitions) != manifest["resource_count"]:
        raise ValidationError("Resource definitions do not cover the exported pack")
    report=dict(tool="AoW4 ModKit full RPK build",source_input_sha256=manifest["input_sha256"],
        rebuilt_sha256=hashlib.sha256(data).hexdigest(),binary_template_used=False,
        resources_built=len(project.definitions),reference_compared=False,equivalent=None,
        source_executed_explicitly=True,installed=False,published=False,runtime_tested=False)
    if reference is not None:
        original=read_pack(reference,profile=project.profile)
        result=compare_resource_packs(original._input_bytes,data,profile=project.profile)
        report.update(result,reference_compared=True,reference_sha256=original.source_sha256)
        if not result["equivalent"] and not allow_changes:
            raise ValidationError("Constructed RPK differs from reference; review or explicitly allow intentional changes")
    output=Path(output).absolute()
    sidecar=output.with_suffix(".verification.json")
    if output.suffix.lower() != ".rpk" or output.is_symlink() or sidecar.is_symlink():
        raise ValidationError("Output must be a regular .rpk file and report")
    if reference is not None and output.resolve()==Path(reference).resolve():
        raise ValidationError("Build must not overwrite its comparison reference")
    if output.exists() or sidecar.exists():
        if not output.is_file() or not sidecar.is_file():
            raise ValidationError("Existing output has no complete ownership report")
        prior=json.loads(sidecar.read_text(encoding="utf-8"))
        if prior.get("tool") != report["tool"] or prior.get("source_input_sha256") != manifest["input_sha256"] or prior.get("rebuilt_sha256") != hashlib.sha256(output.read_bytes()).hexdigest():
            raise ValidationError("Existing RPK/report has user changes or another owner")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    sidecar.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report
