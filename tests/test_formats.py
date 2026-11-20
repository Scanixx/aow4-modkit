import struct
import unittest
from uuid import UUID

from aow4modkit.constants import ClassId, ProjectField
from aow4modkit.errors import FormatError, ValidationError
from aow4modkit.formats.binary import FieldTable, encode_string, decode_string
from aow4modkit.formats.acp import ContentProject
from aow4modkit.formats.rpk import ResourcePack, ResourceRecord


class FormatTests(unittest.TestCase):
    def test_noncanonical_directory_and_unknown_payload_survive(self):
        # Directory lists field 9 before field 2; payload order is the reverse.
        raw = bytes([2, 9, 2, 2, 0]) + b"ab" + b"\x00opaque\xff"
        table = FieldTable.read(raw)
        self.assertEqual(table.fields[2], b"ab")
        self.assertEqual(table.write(), raw)

    def test_wide_table_and_utf8(self):
        raw = FieldTable({800: b"a" * 300, 7: encode_string("Příliš žluťoučký")}).write()
        parsed = FieldTable.read(raw)
        self.assertEqual(parsed.write(), raw)
        self.assertEqual(decode_string(parsed.fields[7]), "Příliš žluťoučký")

    def test_malformed_tables_are_rejected(self):
        for raw in [b"", b"\x80", b"\x02\x01", bytes([2, 1, 0, 1, 0]), b"\x00extra"]:
            with self.subTest(raw=raw), self.assertRaises(FormatError):
                FieldTable.read(raw)

    def test_string_lengths_are_not_character_counts(self):
        raw = encode_string("ž")
        self.assertEqual(struct.unpack_from("<I", raw)[0], 2)
        with self.assertRaises(FormatError):
            decode_string(raw + b"x")

    def test_project_is_created_without_template(self):
        project = ContentProject.create(namespace="HELLO", name="Hello", description="Example",
                                        author="Tester", mod_id=UUID(int=1), packs=["HELLO.RPK"])
        project.table.fields[9000] = b"unknown-future-field"
        encoded = project.write()
        parsed = ContentProject.read(encoded)
        self.assertEqual(parsed.write(), encoded)
        self.assertEqual(parsed.table.fields[ProjectField.ID], UUID(int=1).bytes_le)
        self.assertEqual(parsed.table.fields[9000], b"unknown-future-field")

    def test_pack_record_and_dependency_roundtrip(self):
        resource = ResourceRecord.create(ClassId.TRIGGER, 123, "Test", 0, {ClassId.TRIGGER: b"\x00"})
        pack = ResourcePack.create("HELLO.RPK", [resource], ("OTHER.RPK",))
        pack.table.fields[9000] = b"unknown"
        raw = pack.write()
        self.assertEqual(struct.unpack_from("<I", raw, 12)[0], len(raw) - 176)
        parsed = ResourcePack.read(raw)
        parsed.verify_roundtrip()
        self.assertEqual(parsed.write(), raw)
        self.assertEqual(parsed.dependencies, ["OTHER.RPK"])
        self.assertEqual(next(parsed.records())[3].name, "Test")

    def test_unsupported_pack_is_not_silently_accepted(self):
        with self.assertRaises(FormatError):
            ResourcePack.read(b"RPK\x00" + bytes(180))

    def test_duplicate_resource_ids_fail_before_output(self):
        r = ResourceRecord.create(ClassId.TRIGGER, 123, "Test", 0, {ClassId.TRIGGER: b"\x00"})
        with self.assertRaises(ValidationError):
            ResourcePack.create("HELLO.RPK", [r, r])
