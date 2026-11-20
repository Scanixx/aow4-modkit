from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from aow4modkit import DEFAULT_PROFILE, ModProject, Trigger, actions, events, FormatError, ValidationError
from aow4modkit.drift import snapshot, compare_snapshots
from aow4modkit.formats.rpk import ResourcePack


class ProfileTests(unittest.TestCase):
    def test_explicit_profile_controls_wire_header(self):
        # Synthetic profile is a test fixture, not a claim about a future game.
        synthetic = replace(DEFAULT_PROFILE, key="test-only", rpk_signature=b"RPK\x00TEST")
        raw = ResourcePack.create("TEST.RPK", [], profile=synthetic).write()
        with self.assertRaises(FormatError):
            ResourcePack.read(raw)
        self.assertEqual(ResourcePack.read(raw, profile=synthetic).write(), raw)

    def test_profile_can_remove_a_function_and_compilation_fails(self):
        functions = dict(DEFAULT_PROFILE.functions); functions.pop("actions.log")
        profile = replace(DEFAULT_PROFILE, key="test-only", functions=functions)
        p = ModProject("Profile test", "ProfileTest", "0.1", "Tester", "cfbfc69c-fe2b-468c-bd7e-ac99b444bef7", profile=profile)
        p.add_trigger(Trigger("log", [events.new_turn()], [actions.log("hello")]))
        with self.assertRaisesRegex(ValidationError, "unavailable in profile"):
            p.plan()

    def test_snapshot_distinguishes_hash_and_structure_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "example.rpk"
            pack = ResourcePack.create("TEST.RPK", [])
            path.write_bytes(pack.write()); before = snapshot([path])
            # Same fields, different content: not proof of a wire-format change.
            pack.table.fields[22] = b"\x05\x00\x00\x00OTHER"
            path.write_bytes(pack.write()); content = snapshot([path])
            result = compare_snapshots(before, content)
            self.assertEqual(result["changes"][0]["change"], "content_hash_only")
            self.assertIsNone(result["compatible"])
            pack.table.fields[999] = b"new"
            path.write_bytes(pack.write()); structural = snapshot([path])
            self.assertEqual(compare_snapshots(content, structural)["changes"][0]["change"], "structural_review")

    def test_unsupported_header_is_a_review_signal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "future.rpk"; path.write_bytes(b"RPK\x00unsupported")
            result = snapshot([path])
            self.assertEqual(result["files"]["future.rpk"]["format"], "unsupported")
