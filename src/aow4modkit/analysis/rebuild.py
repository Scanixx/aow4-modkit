"""Explicit rebuild of trusted exported Python, scoped to trigger fields."""
import hashlib
import json
from pathlib import Path
import runpy
from uuid import UUID

from ..compiler import Trigger as AuthoredTrigger, Script as AuthoredScript, TriggerCompiler
from ..constants import ClassId as C
from ..errors import ValidationError
from ..formats.binary import FieldTable
from ..formats.rpk import ResourcePack, ResourceRecord
from ..profiles import DEFAULT_PROFILE, get_profile
from .reader import decode_pack
from .equivalence import compare_trigger_packs


def _patch_record(record, scripts):
    if record.class_id == C.TRIGGER:
        holder = record.class_fields()
        holder.fields[0] = scripts["global"]
        record.table.fields[C.TRIGGER] = holder.write()
    elif record.class_id == C.STORY_EVENT:
        base = record.class_fields(C.STORY_EVENT_BASE)
        base.fields[1] = scripts["initialization"]
        record.table.fields[C.STORY_EVENT_BASE] = base.write()
        event = record.class_fields()
        holder = FieldTable.read(event.fields[4])
        groups = FieldTable.read(holder.fields[1])
        rows = FieldTable.read(groups.fields[1])
        for index, raw in list(rows.fields.items()):
            button = ResourceRecord.read(raw)
            button.table.fields[2] = scripts[f"choice[{index}].action"]
            button.table.fields[6] = scripts[f"choice[{index}].visibility"]
            rows.fields[index] = button.write()
        groups.fields[1] = rows.write(); holder.fields[1] = groups.write()
        event.fields[4] = holder.write(); record.table.fields[C.STORY_EVENT] = event.write()
    else:
        raise ValidationError("No registered script writer for this resource class")


def rebuild_trigger_pack(data: bytes, definitions: dict, *, mod_id, profile=DEFAULT_PROFILE):
    """Compile all registered scripts; preserve other pack content as a template.

    definitions maps original script paths to public Trigger/Script objects.
    The original UUID is supplied explicitly, never invented from an RPK.
    Does not load Python or write files. Modified definitions are allowed;
    call compare_trigger_packs to determine equivalence separately.
    """
    from .python_export import validate_trigger_export
    original = decode_pack(data, profile=profile)
    validate_trigger_export(original)
    if not isinstance(definitions, dict) or set(definitions) != {s.path for s in original.scripts}:
        raise ValidationError("Definitions must cover every registered script path exactly once")
    try:
        identity = mod_id if isinstance(mod_id, UUID) else UUID(str(mod_id))
    except (ValueError, TypeError) as exc:
        raise ValidationError("Rebuild requires an explicit valid project UUID") from exc
    compilers, compiled = {}, {}
    for script in original.scripts:
        definition = definitions[script.path]
        expected = AuthoredScript if script.role != "global" else AuthoredTrigger
        if not isinstance(definition, expected) or (script.role == "global" and definition.embedded):
            raise ValidationError(f"Wrong Trigger/Script kind at {script.path}")
        if definition.context != script.context:
            raise ValidationError("Changing a script's native context requires a separate schema review")
        uid = int(script.resource_id, 16)
        if script.role == "global" and definition.resource_id != uid:
            raise ValidationError("Global trigger resource ID must remain pinned")
        if script.role == "global" and definition.name not in (None, script.resource_name):
            raise ValidationError("Resource names are outside the trigger-only rebuild scope")
        if script.role != "global" and definition.resource_id not in (None, uid):
            raise ValidationError("Embedded script ownership is fixed by its containing resource")
        compiler = compilers.setdefault(uid, TriggerCompiler(identity, uid, profile))
        compiled.setdefault(uid, {})[script.role] = compiler.compile_script(definition)
    pack = ResourcePack.read(data, profile=profile)
    for store, group, index, record in list(pack.records()):
        if record.resource_id in compiled:
            _patch_record(record, compiled[record.resource_id])
            pack.replace_record(store, group, index, record)
    return pack.write()


def rebuild_export(directory, output, *, mod_id=None, allow_changes=False):
    """Explicitly execute trusted exported Python and write a checked RPK.

    Same trust boundary as ModKit's existing Python project build command.
    Inspection/export never calls this function automatically.
    """
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "export-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("tool") != "AoW4 ModKit trigger Python export":
        raise ValidationError("Directory is not a trigger Python export")
    identity = mod_id or manifest.get("mod_id")
    if identity is None:
        raise ValidationError("Supply the original mod UUID with --mod-id; RPK does not establish it")
    template = directory / "input.rpk"
    raw = template.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["input_sha256"]:
        raise ValidationError("Input template differs from its exported hash")
    output = Path(output).absolute()
    if output.resolve() == template.resolve() or output.suffix.lower() != ".rpk":
        raise ValidationError("Output must be a separate .rpk file")
    # This is the sole source-execution step, requested explicitly by the user.
    builder = runpy.run_path(str(directory / "triggers.py"))["build_triggers"]
    definitions = builder()
    profile = get_profile(manifest["profile"])
    rebuilt = rebuild_trigger_pack(raw, definitions, mod_id=identity, profile=profile)
    report = compare_trigger_packs(raw, rebuilt, profile=profile)
    report.update(input_sha256=manifest["input_sha256"], rebuilt_sha256=hashlib.sha256(rebuilt).hexdigest(),
                  tool="AoW4 ModKit trigger rebuild", mod_id=str(identity), source_executed_explicitly=True, installed=False, published=False)
    if not report["equivalent"] and not allow_changes:
        raise ValidationError("Rebuilt scripts differ; use --allow-changes only for intentional edits")
    sidecar = output.with_suffix(".verification.json")
    if output.is_symlink() or sidecar.is_symlink():
        raise ValidationError("Rebuild outputs must not be symbolic links")
    if output.exists() or sidecar.exists():
        if not output.is_file() or not sidecar.is_file():
            raise ValidationError("Existing output/report has no complete ownership record; choose another filename")
        prior = json.loads(sidecar.read_text(encoding="utf-8"))
        if prior.get("tool") != "AoW4 ModKit trigger rebuild" or prior.get("input_sha256") != manifest["input_sha256"] or prior.get("rebuilt_sha256") != hashlib.sha256(output.read_bytes()).hexdigest():
            raise ValidationError("Existing output has user changes or belongs to another input")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rebuilt)
    sidecar.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report
