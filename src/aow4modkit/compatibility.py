"""Build-time declarations: target AoW4 2.3.x, independently optional DLC.

This module checks declared requirements and optional file availability. It does
not query Steam ownership or prove that a mod works in an engine session.
"""
from dataclasses import dataclass
from pathlib import Path
import re

from .errors import ValidationError

TARGET_GAME_SERIES = "2.3.*"


@dataclass(frozen=True)
class DlcRequirement:
    key: str
    title: str
    content_folder: str
    minimum_game_version: str | None = None

    def __post_init__(self):
        if not self.key or not self.title or not re.fullmatch(r"[A-Za-z0-9_-]+", self.content_folder):
            raise ValidationError("DLC needs a key, title and a single content-folder name")
        if self.minimum_game_version and not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", self.minimum_game_version):
            raise ValidationError("DLC minimum game version must look like 2.3.0")


def compatibility_report(*, requirements: tuple[DlcRequirement, ...],
                         external_references: list[dict], game_version: str | None = None,
                         game_dir: Path | None = None, notes: tuple[str, ...] = (),
                         target_series: str = TARGET_GAME_SERIES) -> dict:
    """Report only requirements used by the project. Missing DLC never blocks
    serialization. Authors should review warnings before distributing the ZIP.
    ``game_dir`` means the game root, containing ``Content``.
    """
    if not re.fullmatch(r"\d+\.\d+\.\*", target_series):
        raise ValidationError("Profile target series must look like 2.3.*")
    baseline = target_series[:-1] + "0"
    target_pair = tuple(map(int, target_series.split(".")[:2]))
    warnings = []
    if game_version is None:
        warnings.append({"code": "GAME_VERSION_NOT_CHECKED", "message":
            f"Target is Age of Wonders 4 {target_series}; installed game version was not supplied."})
    elif not re.fullmatch(r"\d+\.\d+(?:\.\d+)*(?:[A-Za-z0-9+._-]*)?", game_version):
        raise ValidationError("Game version must look like 2.3.0; supply the actual version, not a wildcard")
    elif tuple(map(int, re.match(r"^(\d+)\.(\d+)", game_version).groups())) != target_pair:
        warnings.append({"code": "OUTSIDE_TARGET_SERIES", "message":
            f"Supplied game version {game_version} is outside the declared {target_series} target. Forward compatibility is not claimed."})
    required = []
    for dlc in sorted(set(requirements), key=lambda d: d.key):
        state = "not_checked"
        if game_dir is not None:
            state = "files_present" if (game_dir / "Content" / dlc.content_folder).is_dir() else "files_missing"
        required.append({"key": dlc.key, "title": dlc.title, "file_availability": state})
        if dlc.minimum_game_version:
            parts = lambda s: tuple(int(x or 0) for x in re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", s).groups())
            required[-1]["minimum_game_version"] = dlc.minimum_game_version
            if parts(dlc.minimum_game_version) > parts(baseline):
                warnings.append({"code": "DLC_NEWER_THAN_TARGET", "message":
                    f"{dlc.title} requires {dlc.minimum_game_version}, newer than the base {baseline} target. Review the mod's required patch version."})
            if game_version and parts(game_version) < parts(dlc.minimum_game_version):
                warnings.append({"code": "GAME_TOO_OLD_FOR_DLC", "message":
                    f"Supplied game version is older than {dlc.title}'s declared minimum {dlc.minimum_game_version}."})
        if state != "files_present":
            warnings.append({"code": "DLC_FILES_MISSING" if state == "files_missing" else "DLC_NOT_CHECKED",
                             "message": f"{dlc.title} is required by referenced content; files are {state.replace('_', ' ')}. Build can continue; players need the DLC."})
    for reference in external_references:
        if reference.get("kind", "other") == "other":
            warnings.append({"code": "REFERENCE_KIND_UNVERIFIED", "message":
                f"The binary resource kind of {reference['name']} is not declared; type-level link checks cannot prove engine semantics."})
        if game_dir is None:
            state = "not_checked"
        else:
            matches = list((game_dir / "Content").rglob(reference["pack"]))
            state = "pack_present" if matches else "pack_missing"
        reference["file_availability"] = state
        if state == "pack_missing":
            warnings.append({"code": "EXTERNAL_PACK_MISSING", "message":
                f"Referenced pack {reference['pack']} was not found. Resource existence and semantics are not verified."})
    titles = [d["title"] for d in required]
    description = [f"Designed for Age of Wonders 4 {target_series.replace('*', 'x')}."]
    if titles:
        description.append("Requires: " + ", ".join(titles) + ".")
    else:
        description.append("This project declares no DLC requirements.")
    description.append("DLC file availability does not verify Steam ownership or runtime compatibility.")
    return {"target_game_series": target_series, "supplied_game_version": game_version,
            "runtime_tested": False, "required_dlc": required,
            "external_references": external_references, "warnings": warnings,
            "author_notes": list(notes), "suggested_description": "\n".join(description)}
