"""The observed CPR/TEUserContentProjectData project wrapper."""
from dataclasses import dataclass
from uuid import UUID

from .binary import FieldTable, U32, encode_string, encode_strings
from ..constants import ProjectField
from ..errors import FormatError
from ..profiles import DEFAULT_PROFILE, GameProfile

PROJECT_PREFIX = DEFAULT_PROFILE.acp_prefix
PROJECT_HEADER_SIZE = len(PROJECT_PREFIX)


@dataclass
class ContentProject:
    prefix: bytes
    table: FieldTable
    profile: GameProfile = DEFAULT_PROFILE

    @classmethod
    def read(cls, raw: bytes, *, profile: GameProfile = DEFAULT_PROFILE) -> "ContentProject":
        size = len(profile.acp_prefix)
        if len(raw) <= size or raw[:4] != profile.acp_prefix[:4]:
            raise FormatError("Unsupported or truncated ACP header")
        start = profile.acp_class_offset
        if raw[start:start+len(profile.acp_class_signature)] != profile.acp_class_signature:
            raise FormatError("Unsupported ACP project class")
        return cls(raw[:size], FieldTable.read(raw, size), profile)

    def write(self) -> bytes:
        return self.prefix + self.table.write()

    @classmethod
    def create(cls, *, namespace: str, name: str, description: str, author: str,
               mod_id: UUID, packs: list[str], thumbnail: str | None = None,
               profile: GameProfile = DEFAULT_PROFILE) -> "ContentProject":
        fields = {
            ProjectField.NAMESPACE: encode_string(namespace),
            ProjectField.NAME: encode_string(name),
            ProjectField.DESCRIPTION: encode_string(description),
            ProjectField.AUTHOR: encode_string(author),
            ProjectField.PROFILE_24: U32.pack(2),
            ProjectField.PROFILE_25: encode_string(""),
            ProjectField.PACKS: encode_strings(packs),
            ProjectField.PROFILE_31: U32.pack(3),
            ProjectField.PROFILE_39: U32.pack(2),
            ProjectField.PROFILE_40: U32.pack(2),
            ProjectField.ID: mod_id.bytes_le,
        }
        if thumbnail:
            fields[ProjectField.THUMBNAIL] = encode_string(thumbnail)
        return cls(profile.acp_prefix, FieldTable(dict(sorted(fields.items()))), profile)
