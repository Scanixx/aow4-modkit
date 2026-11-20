"""Load independently extensible DLC/reference definitions from JSON.

Catalogs contain IDs, names and requirements, never embedded game resources.
Adding content of a known kind needs no change to the binary serializer.
New binary classes still need a separate schema implementation and tests.
"""
import json
from importlib.resources import files
from pathlib import Path
import re

from .compatibility import DlcRequirement
from .errors import ValidationError
from .expressions import ResourceRef

CONTENT_FORMAT_VERSION = 1
SUPPORTED_REFERENCE_KINDS = {"racial_transformation", "hero_skill", "side_property", "token", "other",
                             "icon", "ai_priority", "hero_skill_group"}


class ContentCatalog:
    def __init__(self):
        self._references: dict[str, ResourceRef] = {}
        self._definitions: dict[str, dict] = {}

    def load(self, path: str | Path) -> "ContentCatalog":
        """Add one authored DLC definition. Duplicate keys/IDs are rejected,
        rather than silently changing the meaning of an existing reference.
        """
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationError(f"Cannot read content definition {path}: {exc}") from exc
        return self._merge(data)

    def load_builtin(self, key: str) -> "ContentCatalog":
        """Load one separately packaged JSON definition, without a game install."""
        if not re.fullmatch(r"[a-z0-9_]+", key):
            raise ValidationError("Builtin content key must use lowercase letters, digits or underscores")
        try:
            raw = files("aow4modkit").joinpath("content_definitions", key + ".json").read_text(encoding="utf-8")
        except OSError as exc:
            raise ValidationError(f"Unknown builtin content definition: {key}") from exc
        return self._merge(json.loads(raw))

    def _merge(self, data) -> "ContentCatalog":
        if not isinstance(data, dict) or data.get("format_version") != CONTENT_FORMAT_VERSION:
            raise ValidationError("Unsupported content definition version; expected format_version 1")
        if not isinstance(data.get("resources"), list):
            raise ValidationError("Content definition needs a resources array")
        dlc = data.get("dlc")
        try:
            requirement = DlcRequirement(**dlc) if dlc is not None else None
            pending = {}
            existing_ids = {ref.resource_id for ref in self._references.values()}
            for item in data["resources"]:
                key = item["key"]
                if not isinstance(key, str) or not key or key in pending or key in self._references:
                    raise ValidationError(f"Duplicate or invalid content key: {key}")
                if item.get("kind", "other") not in SUPPORTED_REFERENCE_KINDS:
                    raise ValidationError(f"Unsupported reference kind for {key}")
                ident = item["id"]
                ident = int(ident, 16) if isinstance(ident, str) else ident
                if ident in existing_ids:
                    raise ValidationError(f"Duplicate resource ID in content catalogs: {ident:016X}")
                existing_ids.add(ident)
                pending[key] = ResourceRef(ident, item["name"], item["url"], item["pack"], requirement, item.get("kind", "other"))
        except (TypeError, KeyError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"Malformed content definition: {exc}") from exc
        self._references.update(pending)
        self._definitions.update({item["key"]: item for item in data["resources"]})
        return self

    def ref(self, key: str) -> ResourceRef:
        try:
            return self._references[key]
        except KeyError as exc:
            raise ValidationError(f"Unknown content key: {key}") from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._references))
