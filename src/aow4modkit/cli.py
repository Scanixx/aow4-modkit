"""Command-line interface. No installation, editor automation or publishing."""
import argparse
import json
from pathlib import Path
import runpy
import sys
from uuid import uuid4

from .errors import ModKitError, ValidationError
from .formats.acp import ContentProject
from .formats.binary import decode_string
from .formats.rpk import ResourcePack
from .constants import ProjectField, ResourceField
from .project import ModProject, build, TOOL_VERSION
from .schema import FUNCTIONS
from .templates import HELLO_SOURCE
from .profiles import DEFAULT_PROFILE, PROFILES, get_profile
from .drift import snapshot, compare_snapshots


def load_project(path: str | Path) -> ModProject:
    """Execute the author's Python source explicitly; never use this for RPK."""
    source = Path(path).resolve()
    if source.suffix != ".py":
        raise ValidationError("Project source must be a trusted .py file")
    values = runpy.run_path(str(source), run_name="aow4modkit_project")
    project = values.get("project")
    if not isinstance(project, ModProject):
        raise ValidationError("Source must define a ModProject named 'project'")
    return project


def inspect_file(path: str | Path, *, profile=DEFAULT_PROFILE) -> dict:
    """Read containers and resource metadata. No executable project loading."""
    raw = Path(path).read_bytes()
    if raw[:4] == b"CPR\x00":
        project = ContentProject.read(raw, profile=profile)
        return {"format": "ACP", "name": decode_string(project.table.fields[ProjectField.NAME]),
                "field_ids": [int(k) for k in project.table.fields]}
    pack = ResourcePack.read(raw, profile=profile)
    pack.verify_roundtrip()
    resources = [{"id": f"{r.resource_id:016X}", "name": r.name, "class_id": f"{r.class_id:08X}",
                  "url": decode_string(r.table.fields[ResourceField.URL]),
                  "field_ids": [int(k) for k in r.table.fields]}
                 for *_, r in pack.records()]
    return {"format": "RPK", "dependencies": pack.dependencies, "resources": resources}


def function_reference() -> str:
    """Generate the function reference from the same registry as validation."""
    lines = ["# Supported trigger functions", "", "Generated from `schema.FUNCTIONS`. This is a subset, not the full engine API.", ""]
    for name, spec in sorted(FUNCTIONS.items()):
        lines.extend([f"## `{name}`", "", spec.description, "",
                      f"Serialized function: `{int(spec.data_type)}:{spec.function_id}`. Result: `{spec.data_type.name}`.", ""])
        if spec.parameters:
            lines.extend(["| Slot | Parameter | Type |", "|---|---|---|"])
            lines.extend(f"| {i} | {p.name} | {p.data_type.name} |" for i, p in enumerate(spec.parameters, 1))
            lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="aow4modkit", description="Python mod authoring and migration for AoW4 2.3.x")
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a no-DLC example with a fresh project UUID")
    init.add_argument("directory", type=Path)
    for name in ("validate", "build", "package"):
        command = commands.add_parser(name, help=f"{name.capitalize()} a trusted Python project")
        command.add_argument("source", type=Path)
        command.add_argument("--game-version", help="Actual game version, e.g. 2.3.0; not auto-detected")
        command.add_argument("--game-dir", type=Path, help="Optional game root for read-only DLC file checks")
        command.add_argument("--profile", help="Explicit named serializer profile; source project default is otherwise used")
        if name != "validate":
            command.add_argument("--output", type=Path, help="Defaults to artifacts beside the source")
    inspector = commands.add_parser("inspect", help="Read supported RPK/ACP metadata; no decompilation")
    inspector.add_argument("file", type=Path)
    inspector.add_argument("--profile", default=DEFAULT_PROFILE.key)
    inspector.add_argument("--detail", action="store_true", help="Decode registered RPK trigger locations as analysis JSON")
    decoder = commands.add_parser("decode", help="Write nonexecuting RPK trigger analysis, exact input copy and readable outlines")
    decoder.add_argument("file", type=Path)
    decoder.add_argument("--profile", default=DEFAULT_PROFILE.key)
    decoder.add_argument("--output", required=True, type=Path)
    exporter = commands.add_parser("export-python", help="Strict public-API Python export of registered RPK triggers")
    exporter.add_argument("file", type=Path)
    exporter.add_argument("--output", required=True, type=Path)
    exporter.add_argument("--mod-id", help="Explicit original project UUID; optional until rebuild")
    exporter.add_argument("--profile", default=DEFAULT_PROFILE.key)
    exporter.add_argument("--scope",choices=("triggers","pack"),default="triggers",help="pack exports all supported resources without a binary template")
    rebuilder = commands.add_parser("rebuild-triggers", help="Explicitly execute trusted exported Python and rebuild its trigger RPK")
    rebuilder.add_argument("directory", type=Path)
    rebuilder.add_argument("--output", required=True, type=Path)
    rebuilder.add_argument("--mod-id")
    rebuilder.add_argument("--allow-changes", action="store_true")
    pack_builder=commands.add_parser("build-pack",help="Explicit trusted Python construction of a complete RPK without a template")
    pack_builder.add_argument("directory",type=Path)
    pack_builder.add_argument("--output",required=True,type=Path)
    pack_builder.add_argument("--reference",type=Path)
    pack_builder.add_argument("--allow-changes",action="store_true")
    commands.add_parser("functions", help="Print Markdown reference for the supported function registry")
    commands.add_parser("profiles", help="List explicitly supported serializer profiles")
    snap = commands.add_parser("snapshot", help="Hash selected files and record recognized structural inventories")
    snap.add_argument("files", nargs="+", type=Path)
    snap.add_argument("--output", required=True, type=Path)
    snap.add_argument("--profile", default=DEFAULT_PROFILE.key)
    snap.add_argument("--game-version")
    snap.add_argument("--editor-version")
    diff = commands.add_parser("compare-snapshots", help="Report changes for manual update review, not a compatibility verdict")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            directory = args.directory
            if directory.exists() and any(directory.iterdir()):
                raise ValidationError("Init requires an empty or new directory")
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "mod.py").write_text(HELLO_SOURCE.format(mod_id=uuid4()), encoding="utf-8")
            (directory / "README.md").write_text("# Your first mod\n\nEdit `mod.py`, then run `python -m aow4modkit package mod.py`.\nSee the ModKit quickstart for installation, test and removal instructions.\n", encoding="utf-8")
            print(f"Created {directory / 'mod.py'} with a fresh UUID. Edit its name, folder and author.")
        elif args.command == "inspect":
            if args.detail:
                from .analysis import read_pack
                result = read_pack(args.file, profile=get_profile(args.profile))
                print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
                return 3 if result.statistics["errors"] else 0
            print(json.dumps(inspect_file(args.file, profile=get_profile(args.profile)), indent=2, ensure_ascii=False))
        elif args.command == "decode":
            from .analysis import read_pack, write_analysis
            source = args.file.resolve()
            output = args.output.absolute()
            if source.is_relative_to(output.resolve()):
                raise ValidationError("Analysis output must not contain its input file")
            result = read_pack(source, profile=get_profile(args.profile))
            directory = write_analysis(result, output)
            print(json.dumps({"directory": str(directory), "analysis_only": True, "statistics": result.statistics}, indent=2))
            return 3 if result.statistics["errors"] else 0
        elif args.command == "export-python":
            from .analysis import read_pack, export_trigger_python, export_pack_python
            source = args.file.resolve()
            if source.is_relative_to(args.output.resolve()):
                raise ValidationError("Export directory must not contain its input")
            pack = read_pack(source, profile=get_profile(args.profile))
            manifest = (export_pack_python if args.scope == "pack" else export_trigger_python)(pack, args.output, mod_id=args.mod_id)
            print(json.dumps({"directory": str(args.output), "scripts": manifest["script_count"],
                              "scope": manifest.get("scope",args.scope), "equivalence_status": manifest["equivalence_status"]}, indent=2))
        elif args.command == "build-pack":
            from .analysis import build_pack_export
            print(json.dumps(build_pack_export(args.directory,args.output,reference=args.reference,allow_changes=args.allow_changes),indent=2))
        elif args.command == "rebuild-triggers":
            from .analysis import rebuild_export
            report = rebuild_export(args.directory, args.output, mod_id=args.mod_id, allow_changes=args.allow_changes)
            print(json.dumps(report, indent=2))
        elif args.command == "functions":
            print(function_reference())
        elif args.command == "profiles":
            print(json.dumps([{"key": p.key, "game_series": p.game_series} for p in PROFILES.values()], indent=2))
        elif args.command == "snapshot":
            if args.output.resolve() in {p.resolve() for p in args.files}:
                raise ValidationError("Snapshot output must not overwrite a source file")
            data = snapshot(args.files, profile=get_profile(args.profile),
                            game_version=args.game_version, editor_version=args.editor_version)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(args.output)
        elif args.command == "compare-snapshots":
            before = json.loads(args.before.read_text(encoding="utf-8"))
            after = json.loads(args.after.read_text(encoding="utf-8"))
            print(json.dumps(compare_snapshots(before, after), indent=2))
        else:
            project = load_project(args.source)
            if args.profile:
                project.profile = get_profile(args.profile)
            if args.command == "validate":
                plan = project.plan(game_version=args.game_version, game_dir=args.game_dir)
                print(json.dumps({"valid": True, "resources": plan["resources"],
                                  "dependencies": plan["dependencies"], "compatibility": plan["compatibility"]}, indent=2))
            else:
                output = args.output or args.source.resolve().parent / "artifacts"
                result = build(project, output, package=args.command == "package",
                               game_version=args.game_version, game_dir=args.game_dir)
                print(json.dumps({"directory": str(result.directory),
                                  "archive": str(result.archive) if result.archive else None,
                                  "compatibility": result.compatibility}, indent=2))
        return 0
    except (ModKitError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
