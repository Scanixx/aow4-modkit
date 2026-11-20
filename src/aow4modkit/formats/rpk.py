"""Observed RPK container profile and opaque resource records.

Constructors encode the supported profile directly: no template mod, game
assets, installed editor, native executable or older build is required.
"""
from dataclasses import dataclass

from .binary import FieldTable, U32, U64, encode_string, decode_string, encode_strings, decode_strings
from ..constants import ClassId, PackField, StoreField, ResourceField
from ..errors import FormatError, ValidationError
from ..profiles import DEFAULT_PROFILE, GameProfile

RPK_SIGNATURE = DEFAULT_PROFILE.rpk_signature
RPK_HEADER_SIZE = DEFAULT_PROFILE.rpk_header_size
STORE_HEADERS = DEFAULT_PROFILE.store_headers
STORE_HEADER_SIZE = 13
# These small serializer defaults are structural metadata, not game resources.
# Their semantics are not fully inferred; preserve rather than reinterpret them.
EDITOR_DATA = bytes.fromhex("0613001404150e18121c161d1a08000000060000004e4f4e414d4501010000010100000101000000")
PROFILE_35 = bytes.fromhex("8001000000111440000000000000")


@dataclass
class ResourceRecord:
    """One class ID and field table; class-specific payloads stay opaque."""
    class_id: int
    table: FieldTable

    @classmethod
    def read(cls, data: bytes) -> "ResourceRecord":
        if len(data) < 5:
            raise FormatError("Truncated resource record")
        return cls(U32.unpack_from(data)[0], FieldTable.read(data, 4))

    def write(self) -> bytes:
        return U32.pack(self.class_id) + self.table.write()

    @property
    def resource_id(self) -> int:
        raw = self.table.fields.get(ResourceField.ID, b"")
        if len(raw) != 8:
            raise FormatError("Resource ID must occupy eight bytes")
        return U64.unpack(raw)[0]

    @property
    def name(self) -> str:
        return decode_string(self.table.fields.get(ResourceField.NAME, b""))

    def class_fields(self, class_id: int | None = None) -> FieldTable:
        return FieldTable.read(self.table.fields[self.class_id if class_id is None else class_id])

    @classmethod
    def create(cls, class_id: int, resource_id: int, name: str, index: int,
               classes: dict[int, bytes]) -> "ResourceRecord":
        fields = {
            ResourceField.TAGS: FieldTable({ClassId.RESOURCE_TAGS: FieldTable({}).write()}).write(),
            ResourceField.URL: encode_string(f"[#{resource_id:016X}]0\\{index}"),
            ResourceField.NAME: encode_string(name),
            ResourceField.ID: U64.pack(resource_id),
            ResourceField.ENABLED: b"\x01",
        }
        fields.update(classes)
        return cls(class_id, FieldTable(fields))


@dataclass
class ContentStore:
    prefix: bytes
    manager: FieldTable
    profile: GameProfile = DEFAULT_PROFILE

    @classmethod
    def read(cls, data: bytes, *, profile: GameProfile = DEFAULT_PROFILE) -> "ContentStore":
        size = len(profile.store_headers[0])
        if data[:size] not in profile.store_headers:
            raise FormatError("Unsupported content-store header; no schema was guessed")
        return cls(data[:size], FieldTable.read(data, size), profile)

    def write(self) -> bytes:
        return self.prefix + self.manager.write()

    def records(self):
        if StoreField.RESOURCE_GROUPS not in self.manager.fields:
            raise FormatError("Content store is missing its resource groups field")
        groups = FieldTable.read(self.manager.fields[StoreField.RESOURCE_GROUPS])
        for group, raw in groups.fields.items():
            for index, record in FieldTable.read(raw).fields.items():
                yield group, index, ResourceRecord.read(record)


@dataclass
class ResourcePack:
    """An RPK of the observed signature, retaining unknown top-level fields."""
    prefix: bytes
    table: FieldTable
    profile: GameProfile = DEFAULT_PROFILE

    @classmethod
    def read(cls, data: bytes, *, profile: GameProfile = DEFAULT_PROFILE) -> "ResourcePack":
        size = profile.rpk_header_size
        if len(data) < size + 1 or data[:len(profile.rpk_signature)] != profile.rpk_signature:
            raise FormatError("Unsupported or truncated RPK header")
        if U32.unpack_from(data, profile.rpk_length_offset)[0] != len(data) - size:
            raise FormatError("RPK payload length does not match file length")
        return cls(data[:size], FieldTable.read(data, size), profile)

    def write(self) -> bytes:
        payload = self.table.write()
        header = bytearray(self.prefix)
        if len(header) != self.profile.rpk_header_size:
            raise FormatError("Unexpected RPK header size")
        U32.pack_into(header, self.profile.rpk_length_offset, len(payload))
        return bytes(header) + payload

    def stores(self):
        if PackField.STORES not in self.table.fields:
            raise FormatError("Pack is missing its content stores field")
        for key, raw in FieldTable.read(self.table.fields[PackField.STORES]).fields.items():
            yield key, ContentStore.read(raw, profile=self.profile)

    def records(self):
        for store_id, store in self.stores():
            for group, index, record in store.records():
                yield store_id, group, index, record

    @property
    def dependencies(self) -> list[str]:
        return decode_strings(self.table.fields.get(PackField.DEPENDENCIES, U32.pack(0)))

    def verify_roundtrip(self) -> None:
        """Check every supported container layer, not only an opaque pass-through."""
        for _, store in self.stores():
            parsed = ContentStore.read(store.write(), profile=self.profile)
            if parsed.write() != store.write():
                raise FormatError("Content store does not round-trip")
            raw_groups = store.manager.fields[StoreField.RESOURCE_GROUPS]
            groups = FieldTable.read(raw_groups)
            if groups.write() != raw_groups:
                raise FormatError("Resource groups do not round-trip")
            for raw_records in groups.fields.values():
                if FieldTable.read(raw_records).write() != raw_records:
                    raise FormatError("Record directory does not round-trip")
            for _, _, record in store.records():
                if ResourceRecord.read(record.write()).write() != record.write():
                    raise FormatError("Resource does not round-trip")
        encoded = self.write()
        if ResourcePack.read(encoded, profile=self.profile).write() != encoded:
            raise FormatError("Pack does not round-trip")

    @classmethod
    def create(cls, name: str, records: list[ResourceRecord],
               dependencies: tuple[str, ...] = (), *, profile: GameProfile = DEFAULT_PROFILE) -> "ResourcePack":
        """Build the supported one-store, one-group profile from named inputs."""
        try:
            name_bytes = name.encode("ascii")
        except UnicodeError as exc:
            raise ValidationError("Pack filename must be ASCII") from exc
        if not name_bytes or len(name_bytes) >= profile.rpk_name_capacity or any(c in name for c in "/\\\x00"):
            raise ValidationError("Pack filename must fit its 128-byte header slot")
        ids = [r.resource_id for r in records]
        if len(ids) != len(set(ids)):
            raise ValidationError("Duplicate resource IDs in pack")
        header = bytearray(profile.rpk_header_size)
        header[:len(profile.rpk_signature)] = profile.rpk_signature
        header[profile.rpk_name_offset:profile.rpk_name_offset + len(name_bytes)] = name_bytes
        store = ContentStore(profile.store_headers[0], FieldTable({
            StoreField.PROFILE_19: U32.pack(8),
            StoreField.PROFILE_24: bytes.fromhex("01010000"),
            StoreField.PROFILE_28: bytes.fromhex("01010000"),
            StoreField.PROFILE_29: b"\x00",
            StoreField.NAME: encode_string(name),
            StoreField.RESOURCE_GROUPS: FieldTable({1: FieldTable({
                i: record.write() for i, record in enumerate(records)
            }).write()}).write(),
        }), profile)
        return cls(bytes(header), FieldTable({
            PackField.NAME: encode_string(name),
            PackField.EDITOR_DATA: EDITOR_DATA,
            PackField.PROFILE_29: bytes.fromhex("01010000"),
            PackField.PROFILE_35: PROFILE_35,
            PackField.PROFILE_36: b"\x00",
            PackField.STORES: FieldTable({0: store.write()}).write(),
            PackField.DEPENDENCIES: encode_strings(sorted(set(dependencies))),
        }), profile)
