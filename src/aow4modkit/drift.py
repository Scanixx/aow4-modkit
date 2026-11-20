"""Read-only structural snapshots for reviewing official game/editor updates.

Hash changes alone are not format changes. Structure changes are review signals,
not an automatic incompatibility verdict. No executable is loaded or run.
"""
import hashlib
from pathlib import Path

from .constants import PackField, StoreField
from .errors import ModKitError, FormatError, ValidationError
from .formats.acp import ContentProject
from .formats.binary import FieldTable
from .formats.rpk import ResourcePack
from .profiles import DEFAULT_PROFILE, GameProfile


def snapshot(paths, *, profile: GameProfile = DEFAULT_PROFILE,
             game_version: str | None = None, editor_version: str | None = None) -> dict:
    """Capture authored reference files or selected official binaries as hashes
    and structural field inventories. Snapshot data contains no asset payloads.
    File basenames must be unique to make comparisons unambiguous.
    """
    result = {}
    for path in map(Path, paths):
        if path.name in result:
            raise ValidationError("Snapshot inputs need unique basenames")
        raw = path.read_bytes()
        entry = {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw), "format": "opaque_file"}
        try:
            if raw[:4] == b"RPK\x00":
                pack = ResourcePack.read(raw, profile=profile)
                pack.verify_roundtrip()
                classes = {}
                for *_, resource in pack.records():
                    definition = classes.setdefault(f"{resource.class_id:08X}", {"top_fields": set(), "class_fields": {}})
                    definition["top_fields"].update(resource.table.fields)
                    for key, value in resource.table.fields.items():
                        if key <= 0xFFFF:
                            continue
                        try:
                            table = FieldTable.read(value)
                            if table.write() == value:
                                definition["class_fields"].setdefault(f"{key:08X}", set()).update(table.fields)
                        except FormatError:
                            # Class data can use a different known/unknown encoding.
                            pass
                entry.update({"format": "RPK", "structure": {
                    "signature": raw[:len(profile.rpk_signature)].hex(),
                    "pack_fields": sorted(pack.table.fields),
                    "store_headers": sorted({store.prefix.hex() for _, store in pack.stores()}),
                    "classes": {key: {"top_fields": sorted(v["top_fields"]),
                                      "class_fields": {cid: sorted(fields) for cid, fields in v["class_fields"].items()}}
                                for key, v in sorted(classes.items())}}})
            elif raw[:4] == b"CPR\x00":
                project = ContentProject.read(raw, profile=profile)
                entry.update({"format": "ACP", "structure": {
                    "prefix": project.prefix.hex(), "project_fields": sorted(project.table.fields)}})
        except ModKitError as exc:
            entry.update({"format": "unsupported", "error": str(exc), "observed_prefix": raw[:16].hex()})
        result[path.name] = entry
    return {"snapshot_version": 1, "profile": profile.key, "game_version": game_version,
            "editor_version": editor_version, "files": result,
            "interpretation": "Field inventories are data-dependent; differences require review, not an automatic compatibility verdict."}


def compare_snapshots(before: dict, after: dict) -> dict:
    if before.get("snapshot_version") != 1 or after.get("snapshot_version") != 1:
        raise ValidationError("Unsupported snapshot version")
    changes = []
    old, new = before["files"], after["files"]
    for name in sorted(set(old) | set(new)):
        if name not in old or name not in new:
            changes.append({"file": name, "change": "added" if name in new else "removed"})
            continue
        if old[name] == new[name]:
            continue
        structural = (old[name].get("format"), old[name].get("structure"), old[name].get("error")) != (
            new[name].get("format"), new[name].get("structure"), new[name].get("error"))
        changes.append({"file": name, "change": "structural_review" if structural else "content_hash_only",
                        "before_sha256": old[name]["sha256"], "after_sha256": new[name]["sha256"]})
    return {"before_profile": before["profile"], "after_profile": after["profile"],
            "changes": changes, "requires_manual_review": bool(changes),
            "compatible": None, "interpretation": "This report does not prove compatibility or incompatibility."}
