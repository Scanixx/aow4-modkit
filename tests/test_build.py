from contextlib import redirect_stdout
import gettext
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from aow4modkit import ModProject, Trigger, actions, events, build, ValidationError
from aow4modkit.cli import main, inspect_file


def project():
    p = ModProject("Packaging example", "PackageExample", "0.1", "Tester", "658c91e0-87e0-477f-af6b-7a131ff469c7",
                   tags=("Mod", "Spells", "Units", "Abilities"), messages={"EXAMPLE@NAME": "Ĺ˝luĹĄouÄŤkĂ˝"})
    p.add_trigger(Trigger("hello", [events.new_turn()], [actions.log("hello")]))
    return p


class BuildTests(unittest.TestCase):
    def test_whole_package_and_reproducibility(self):
        p = project()
        with tempfile.TemporaryDirectory() as folder:
            first = build(p, folder, game_version="2.3.0")
            data = first.archive.read_bytes()
            second = build(p, folder, game_version="2.3.0")
            self.assertEqual(second.archive.read_bytes(), data)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                metadata = json.loads(archive.read("PackageExample/.metadata/metadata.json"))
                self.assertEqual(metadata["tags"], ["Mod", "Spells", "Units", "Abilities"])
                catalog = gettext.GNUTranslations(io.BytesIO(archive.read("PackageExample/Language/packageexample.mo")))
                self.assertEqual(catalog.gettext("EXAMPLE@NAME"), "Ĺ˝luĹĄouÄŤkĂ˝")
                manifest = json.loads(archive.read("manifest.json"))
                for name, digest in manifest["payload_sha256"].items():
                    self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                self.assertFalse(any(n.endswith(".py") for n in archive.namelist()))
            info = inspect_file(first.mod_directory / "Packs/packageexample.rpk")
            self.assertEqual(len(info["resources"]), 1)

    def test_unowned_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "PackageExample-0.1"; target.mkdir()
            (target / "precious.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(ValidationError):
                build(project(), folder)
            self.assertEqual((target / "precious.txt").read_text(), "keep")

    def test_path_like_folder_is_rejected(self):
        p = project(); p.folder = "../outside"
        with self.assertRaises(ValidationError):
            p.plan()

    def test_cli_init_validate_package_and_inspect(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            path = Path(folder) / "project"
            self.assertEqual(main(["init", str(path)]), 0)
            self.assertEqual(main(["validate", str(path / "mod.py"), "--game-version", "2.3.0"]), 0)
            self.assertEqual(main(["package", str(path / "mod.py"), "--game-version", "2.3.0"]), 0)
            self.assertTrue((path / "artifacts/HelloRealm-0.1.zip").is_file())
