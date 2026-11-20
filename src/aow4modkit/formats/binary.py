"""Small bounded codecs for observed little-endian field tables."""
from dataclasses import dataclass
import struct

from ..errors import FormatError

U32 = struct.Struct("<I")
U64 = struct.Struct("<Q")
I32 = struct.Struct("<i")
MAX_FIELDS = 100_000


def encode_string(value: str) -> bytes:
    """Encode a UTF-8 string preceded by its byte count (not character count)."""
    raw = value.encode("utf-8")
    return U32.pack(len(raw)) + raw


def decode_string(raw: bytes) -> str:
    """Read a complete counted string, rejecting truncation and trailing data."""
    if len(raw) < U32.size or U32.unpack_from(raw)[0] != len(raw) - U32.size:
        raise FormatError("Expected one complete length-prefixed string")
    try:
        return raw[U32.size:].decode("utf-8")
    except UnicodeError as exc:
        raise FormatError("String contains invalid UTF-8") from exc


def encode_strings(values: list[str] | tuple[str, ...]) -> bytes:
    """Encode the counted string-array layout used by pack dependencies."""
    return U32.pack(len(values)) + b"".join(encode_string(v) for v in values)


def decode_strings(raw: bytes) -> list[str]:
    if len(raw) < 4:
        raise FormatError("Missing string-array count")
    count = U32.unpack_from(raw)[0]
    if count > MAX_FIELDS:
        raise FormatError("String-array count exceeds supported bound")
    cursor, values = 4, []
    for _ in range(count):
        if cursor + 4 > len(raw):
            raise FormatError("Truncated string-array entry")
        length = U32.unpack_from(raw, cursor)[0]
        end = cursor + 4 + length
        if end > len(raw):
            raise FormatError("String-array payload extends outside stream")
        values.append(decode_string(raw[cursor:end]))
        cursor = end
    if cursor != len(raw):
        raise FormatError("Trailing bytes after string array")
    return values


@dataclass
class FieldTable:
    """Opaque values indexed by field ID, preserving parsed directory order.

    A table occupies the remaining bytes from ``offset`` to end-of-stream.
    Unknown values are never interpreted or discarded here. This is not a
    recursive schema inference engine.
    """

    fields: dict[int, bytes]
    narrow_count: int = 0
    entry_order: tuple[int, ...] = ()

    @classmethod
    def read(cls, data: bytes, offset: int = 0) -> "FieldTable":
        if offset < 0 or offset >= len(data):
            raise FormatError("Missing field-table marker")
        marker, cursor = data[offset], offset + 1
        narrow = marker & 0x7F
        wide = 0
        if marker & 0x80:
            if cursor + 4 > len(data):
                raise FormatError("Truncated wide-field count")
            wide = U32.unpack_from(data, cursor)[0]
            cursor += 4
        end_directory = cursor + narrow * 2 + wide * 8
        if narrow + wide > MAX_FIELDS or end_directory > len(data):
            raise FormatError("Invalid field count or truncated directory")
        pairs = [tuple(data[i:i+2]) for i in range(cursor, cursor + narrow * 2, 2)]
        cursor += narrow * 2
        pairs += [struct.unpack_from("<II", data, i)
                  for i in range(cursor, end_directory, 8)]
        if len({key for key, _ in pairs}) != len(pairs):
            raise FormatError("Duplicate field ID")
        order = tuple(key for key, _ in pairs)
        by_offset = sorted(pairs, key=lambda item: item[1])
        payload_size = len(data) - end_directory
        if by_offset and (by_offset[0][1] != 0 or by_offset[-1][1] > payload_size):
            raise FormatError("Field offsets extend outside payload or leave a leading gap")
        if not pairs and payload_size:
            raise FormatError("Unexpected payload after empty field table")
        values = {}
        for index, (key, start) in enumerate(by_offset):
            end = by_offset[index + 1][1] if index + 1 < len(by_offset) else payload_size
            values[key] = data[end_directory + start:end_directory + end]
        return cls(values, narrow, order)

    def write(self) -> bytes:
        """Serialize fields, retaining narrow/wide choices where they still fit."""
        if len(self.fields) > MAX_FIELDS:
            raise FormatError("Too many fields")
        payload, offsets = bytearray(), {}
        for key, value in self.fields.items():
            if not isinstance(key, int) or not 0 <= key <= 0xFFFFFFFF:
                raise FormatError("Field ID must fit unsigned 32 bits")
            if not isinstance(value, bytes):
                raise FormatError(f"Field {key} must contain bytes")
            offsets[key] = len(payload)
            payload.extend(value)
        order = self.entry_order if set(self.entry_order) == set(offsets) else tuple(offsets)
        pairs = [(key, offsets[key]) for key in order]
        narrow = min(self.narrow_count, len(pairs), 127)
        if any(key > 255 or off > 255 for key, off in pairs[:narrow]):
            narrow = 0
        wide = len(pairs) - narrow
        directory = bytearray([narrow | (0x80 if wide else 0)])
        if wide:
            directory.extend(U32.pack(wide))
        for key, off in pairs[:narrow]:
            directory.extend(bytes((key, off)))
        for key, off in pairs[narrow:]:
            directory.extend(struct.pack("<II", key, off))
        return bytes(directory + payload)
