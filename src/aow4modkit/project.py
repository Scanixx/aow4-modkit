"""Project validation, offline build and deterministic publication-ready layout.

This module never installs mods or contacts Workshop/GitHub. Python project
definitions are trusted executable source; RPK inspection does not execute them.
"""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import struct
from uuid import UUID, uuid5
import zipfile

from .compatibility import DlcRequirement, compatibility_report
from .compiler import Trigger, TriggerCompiler
from .constants import DataType
from .errors import ValidationError
from .expressions import Expr, ResourceLink, ResourceRef, OwnedResourceRef
from .resources import ResourceDefinition, ResourceContext
from .formats.acp import ContentProject
from .formats.rpk import ResourcePack
from .localization import compile_messages
from .profiles import GameProfile, DEFAULT_PROFILE

TOOL_VERSION = "0.1.0a4"


def _json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _references(expr: Expr):
    if expr.data_type == DataType.RESOURCE_LINK:
        yield expr.value
    if expr.data_type == DataType.DATA_LIST:
        for child in expr.value[1]:
            yield from _references(child)
    for child in expr.arguments:
        yield from _references(child)


@dataclass
class ModProject:
    """One authored mod. Keep ``mod_id`` and trigger keys stable across updates.

    DLC requirements can be explicit or inferred from used ResourceRefs. Merely
    loading a DLC catalog does not make that DLC required by this project.
    """
    name: str
    folder: str
    version: str
    author: str
    mod_id: UUID | str
    description: str = ""
    tags: tuple[str, ...] = ("Mod",)
    triggers: list[Trigger] = field(default_factory=list)
    resources: list[ResourceDefinition] = field(default_factory=list)
    definition_order: tuple[str, ...] = ()
    pack_name: str | None = None
    catalog_name: str | None = None
    pack_filename: str | None = None
    catalog_filename: str | None = None
    namespace: str | None = None
    short_description: str | None = None
    assets: dict[str, Path] = field(default_factory=dict)
    dependency_manifest: tuple[str, ...] | None = None
    messages: dict[str, str] = field(default_factory=dict)
    thumbnail: Path | None = None
    requires: tuple[DlcRequirement, ...] = ()
    compatibility_notes: tuple[str, ...] = ()
    readme: str = ""
    release_notes: str = ""
    workshop_description: str = ""
    workshop_id: str | None = None
    profile: GameProfile = DEFAULT_PROFILE

    def add_trigger(self, trigger: Trigger) -> None:
        """Register an owned trigger; duplicate keys are rejected during planning."""
        self.triggers.append(trigger)

    def add_resource(self, definition: ResourceDefinition) -> None:
        """Register a named public resource recipe, not an opaque RPK record."""
        if not isinstance(definition, ResourceDefinition):
            raise ValidationError("add_resource() expects a public ResourceDefinition recipe")
        self.resources.append(definition)

    def ref(self, key: str, *, kind="other") -> OwnedResourceRef:
        """Create a forward reference; identity and index URL resolve at planning."""
        return OwnedResourceRef(key, kind)

    def plan(self, *, game_version: str | None = None, game_dir: Path | None = None) -> dict:
        """Validate and serialize in memory. No output folder or game writes."""
        if not isinstance(self.profile, GameProfile):
            raise ValidationError("Project.profile must be a GameProfile")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", self.folder):
            raise ValidationError("Mod folder must be a simple ASCII name starting with a letter (max 80 characters)")
        if not self.name or not self.author:
            raise ValidationError("Project name and author must not be empty")
        if not re.fullmatch(r"\d+(?:\.\d+)+(?:[A-Za-z0-9+._-]*)?", self.version):
            raise ValidationError("Version must look like 0.1 or 0.1.0a4")
        try:
            mod_id = self.mod_id if isinstance(self.mod_id, UUID) else UUID(self.mod_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError("mod_id must be a valid, stable UUID") from exc
        if not self.triggers and not self.resources:
            raise ValidationError("Project needs at least one trigger or resource")
        if any(not isinstance(t, Trigger) or t.embedded for t in self.triggers):
            raise ValidationError("triggers must contain global Trigger definitions, not embedded Scripts")
        if any(not isinstance(r, ResourceDefinition) for r in self.resources):
            raise ValidationError("resources must contain public resource recipes")
        definitions = [*self.resources, *self.triggers]
        by_key = {d.key: d for d in definitions}
        if len(by_key) != len(definitions):
            raise ValidationError("Resource and trigger keys must be unique within a project")
        if self.definition_order:
            if len(self.definition_order) != len(definitions) or set(self.definition_order) != set(by_key):
                raise ValidationError("definition_order must contain every resource/trigger key exactly once")
            definitions = [by_key[key] for key in self.definition_order]
        pack_name = (self.pack_name or self.folder + ".RPK").upper()
        catalog_name = (self.catalog_name or self.folder + ".MO").upper()
        for value, suffix in [(pack_name, ".RPK"), (catalog_name, ".MO")]:
            if not re.fullmatch(r"[A-Z0-9_-]+" + re.escape(suffix), value) or len(value) >= 128:
                raise ValidationError("Pack/catalog filenames must be simple ASCII names with the proper suffix")
        pack_filename = self.pack_filename or pack_name.lower()
        catalog_filename = self.catalog_filename or catalog_name.lower()
        if pack_filename.upper() != pack_name or catalog_filename.upper() != catalog_name:
            raise ValidationError("Output filename overrides must match their pack/catalog name apart from case")
        if any(not isinstance(tag, str) or not tag for tag in self.tags):
            raise ValidationError("Metadata tags must be nonempty strings")
        if self.workshop_id is not None and not re.fullmatch(r"\d+", self.workshop_id):
            raise ValidationError("workshop_id must be a decimal ID string")
        refs, dlcs, bindings = {}, {d.key: d for d in self.requires}, {}
        for index, definition in enumerate(definitions):
            ident = definition.resource_id
            if ident is None:
                ident = int.from_bytes(uuid5(mod_id, "resource:" + definition.key).bytes_le[:8], "little")
            kind = "trigger" if isinstance(definition, Trigger) else definition.kind
            binding = ResourceRef(ident, definition.name or definition.key,
                                  f"[#{ident:016X}]0\\{index}", pack_name, kind=kind)
            if ident in {ref.resource_id for ref in bindings.values()}:
                raise ValidationError("Duplicate owned resource ID")
            bindings[definition.key] = binding
        for definition in definitions:
            if isinstance(definition, Trigger):
                declared = [ref for expr in (*definition.events, *definition.conditions, *definition.actions, *definition.setups)
                            for ref in _references(expr)]
            else:
                declared = definition.references()
            for ref in declared:
                if isinstance(ref, OwnedResourceRef):
                    if ref.key not in bindings:
                        raise ValidationError(f"Unresolved owned reference: {ref.key}")
                    if ref.kind not in ("other", bindings[ref.key].kind):
                        raise ValidationError(f"Owned reference {ref.key} has an incompatible kind")
                    continue
                if isinstance(ref, ResourceLink) and not isinstance(ref, ResourceRef):
                    raise ValidationError("ResourceLink has no declared origin pack; use ResourceRef for a new ModProject")
                if not isinstance(ref, ResourceRef):
                    raise ValidationError("Expected a declared resource reference")
                if ref.resource_id in refs and refs[ref.resource_id] != ref:
                    raise ValidationError(f"Conflicting definitions for reference {ref.resource_id:016X}")
                refs[ref.resource_id] = ref
                if ref.dlc:
                    if ref.dlc.key in dlcs and dlcs[ref.dlc.key] != ref.dlc:
                        raise ValidationError(f"Conflicting DLC definitions for {ref.dlc.key}")
                    dlcs[ref.dlc.key] = ref.dlc
        if set(refs).intersection(r.resource_id for r in bindings.values()):
            raise ValidationError("Owned resource ID collides with an external reference")
        records, resource_info = [], []
        resource_context = ResourceContext(bindings, self.profile, by_key, mod_id) if self.resources else None
        for index, definition in enumerate(definitions):
            ref = bindings[definition.key]
            if isinstance(definition, Trigger):
                compiler = TriggerCompiler(mod_id, ref.resource_id, self.profile, bindings)
                record = compiler.compile(definition, resource_id=ref.resource_id, index=index)
                info = {"nodes": compiler.sequence}
            else:
                record = definition.compile(resource_context)
                info = {"class_id": f"{record.class_id:08X}"}
            records.append(record)
            resource_info.append({"key": definition.key, "id": f"{ref.resource_id:016X}", **info})
        external = [{"id": f"{r.resource_id:016X}", "name": r.name, "url": r.url, "pack": r.pack, "kind": r.kind,
                     "dlc": r.dlc.key if r.dlc else None} for r in sorted(refs.values(), key=lambda r: r.resource_id)]
        compatibility = compatibility_report(requirements=tuple(dlcs.values()), external_references=external,
                                             game_version=game_version, game_dir=Path(game_dir) if game_dir else None,
                                             notes=self.compatibility_notes, target_series=self.profile.game_series)
        dependencies = {r.pack.upper() for r in refs.values()}
        files = {}
        if self.messages:
            dependencies.add(catalog_name)
            files[f"Language/{catalog_filename}"] = compile_messages(self.messages)
        if self.dependency_manifest is not None:
            declared = tuple(self.dependency_manifest)
            if len(set(declared)) != len(declared) or any(not re.fullmatch(r"[A-Z0-9_-]+\.(RPK|MO|CLB)", name) for name in declared):
                raise ValidationError("dependency_manifest needs unique uppercase RPK/MO/CLB filenames")
            if self.messages and catalog_name not in declared:
                raise ValidationError("Preserved dependency manifest must include the localization catalog")
            missing = sorted(dependencies - set(declared))
            compatibility["warnings"].append({"code": "DEPENDENCY_MANIFEST_PRESERVED", "message":
                "The author explicitly preserves a released dependency list and order; resource-origin packs are not automatically appended."})
            compatibility["preserved_dependency_manifest"] = list(declared)
            compatibility["origin_packs_not_declared"] = missing
            dependencies = list(declared)
        pack = ResourcePack.create(pack_name, records, tuple(dependencies), profile=self.profile)
        if self.dependency_manifest is not None:
            from .formats.binary import encode_strings
            from .constants import PackField
            pack.table.fields[PackField.DEPENDENCIES] = encode_strings(list(dependencies))
        pack.verify_roundtrip()
        packed = pack.write()
        files[f"Packs/{pack_filename}"] = packed
        thumbnail_name = None
        if self.thumbnail is not None:
            raw = Path(self.thumbnail).read_bytes()
            if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
                raise ValidationError("Thumbnail must be an existing PNG (no image conversion is performed)")
            if any(not 0 < n <= 16384 for n in struct.unpack_from(">II", raw, 16)):
                raise ValidationError("Thumbnail dimensions are outside supported bounds")
            thumbnail_name = "thumbnail.png"
            files[thumbnail_name] = files[".metadata/thumbnail.png"] = raw
        acp = ContentProject.create(namespace=self.namespace or self.folder.upper(), name=self.name, description=self.description,
                                    author=self.author, mod_id=mod_id, packs=[pack_name], thumbnail=thumbnail_name,
                                    profile=self.profile)
        acp_bytes = acp.write()
        if ContentProject.read(acp_bytes, profile=self.profile).write() != acp_bytes:
            raise ValidationError("Generated ACP failed its round-trip check")
        files[f"{self.folder}.acp"] = acp_bytes
        files[".metadata/metadata.json"] = _json({
            "name": self.name, "id": str(mod_id), "version": self.version,
            "short_description": self.short_description if self.short_description is not None else self.description, "tags": list(dict.fromkeys(self.tags)),
        })
        for relative, path in self.assets.items():
            from pathlib import PurePosixPath
            name = PurePosixPath(relative)
            if not relative or name.as_posix() != relative or name.is_absolute() or ".." in name.parts or "\\" in relative or ":" in relative:
                raise ValidationError("Asset paths must be safe relative POSIX paths")
            if relative.casefold() in {key.casefold() for key in files}:
                raise ValidationError(f"Asset would overwrite a generated file: {relative}")
            files[relative] = Path(path).read_bytes()
        return {"files": files, "compatibility": compatibility, "resources": resource_info,
                "dependencies": list(dependencies) if self.dependency_manifest is not None else sorted(dependencies), "mod_id": str(mod_id), "pack_sha256": _hash(packed),
                "profile": self.profile.key}


@dataclass(frozen=True)
class BuildResult:
    directory: Path
    mod_directory: Path
    archive: Path | None
    compatibility: dict


def build(project: ModProject, output: str | Path, *, package: bool = True,
          game_version: str | None = None, game_dir: str | Path | None = None) -> BuildResult:
    """Write only a named output artifact. ZIP members come from the validated
    in-memory payload, never from an unfiltered recursive directory scan.
    """
    plan = project.plan(game_version=game_version, game_dir=Path(game_dir) if game_dir else None)
    base = Path(output).resolve()
    directory = base / f"{project.folder}-{project.version}"
    mod_directory = directory / project.folder
    payload = {f"{project.folder}/{name}": raw for name, raw in plan["files"].items()}
    compatibility = plan["compatibility"]
    report = {"tool": "AoW4 ModKit", "tool_version": TOOL_VERSION,
              "profile": plan["profile"],
              "name": project.name, "version": project.version, "mod_id": plan["mod_id"],
              "workshop_id": project.workshop_id, "resources": plan["resources"],
              "dependencies": plan["dependencies"], "pack_sha256": plan["pack_sha256"],
              "native_resource_overrides": [], "runtime_tested": False,
              "installed": False, "published": False}
    compatibility_text = compatibility["suggested_description"] + "\n"
    if compatibility["warnings"]:
        compatibility_text += "\nBuild warnings:\n" + "\n".join(
            f"- [{w['code']}] {w['message']}" for w in compatibility["warnings"]) + "\n"
    files = {**payload, "BUILD-REPORT.json": _json(report),
             "COMPATIBILITY.json": _json(compatibility),
             "COMPATIBILITY.txt": compatibility_text.encode("utf-8")}
    if project.readme:
        files["README.txt"] = project.readme.encode("utf-8")
    if project.release_notes:
        files["CHANGELOG.txt"] = project.release_notes.encode("utf-8")
    if project.workshop_description:
        files["WORKSHOP-DESCRIPTION.txt"] = project.workshop_description.encode("utf-8")
    manifest = {"tool": "AoW4 ModKit", "tool_version": TOOL_VERSION,
                "profile": plan["profile"],
                "mod_id": plan["mod_id"], "version": project.version,
                "payload_sha256": {name: _hash(raw) for name, raw in sorted(payload.items())}}
    files["manifest.json"] = _json(manifest)
    # Do not overwrite unrelated files in a pre-existing directory or follow an
    # output-file symlink outside the selected build directory.
    if directory.exists():
        if not directory.resolve().is_relative_to(base):
            raise ValidationError("Build directory points outside the selected output root")
        marker = directory / "manifest.json"
        if not marker.is_file():
            raise ValidationError(f"Output exists without a ModKit manifest: {directory}")
        try:
            prior = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationError("Existing output manifest cannot be read") from exc
        if prior.get("mod_id") != plan["mod_id"] or prior.get("tool") != "AoW4 ModKit":
            raise ValidationError("Output belongs to a different project")
        extras = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()} - set(files)
        if extras:
            raise ValidationError("Output contains stale/unowned files; choose a fresh output directory: " + ", ".join(sorted(extras)))
    for name in files:
        target = directory / name
        if not target.resolve().is_relative_to(directory.resolve()):
            raise ValidationError(f"Output path escapes build directory: {name}")
    directory.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    archive = None
    if package:
        archive = base / f"{project.folder}-{project.version}.zip"
        if archive.is_symlink():
            raise ValidationError("ZIP output must not be a symbolic link")
        if not archive.with_suffix(".zip.sha256").resolve().is_relative_to(base):
            raise ValidationError("Checksum output points outside the selected output root")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
            for name, raw in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                zipped.writestr(info, raw, compresslevel=9)
        with zipfile.ZipFile(archive) as zipped:
            if zipped.testzip() is not None:
                raise ValidationError("ZIP CRC verification failed")
            for name, digest in manifest["payload_sha256"].items():
                if _hash(zipped.read(name)) != digest:
                    raise ValidationError(f"Packaged file hash mismatch: {name}")
        archive.with_suffix(".zip.sha256").write_text(_hash(archive.read_bytes()) + "  " + archive.name + "\n", encoding="ascii")
    return BuildResult(directory, mod_directory, archive, compatibility)
