import json
from pathlib import Path
import tempfile
import unittest

from aow4modkit import ContentCatalog, ModProject, Trigger, actions, events, players, races, ValidationError


def project():
    return ModProject("DLC example", "DlcExample", "0.1", "Tester", "e38ed194-912e-4281-af1e-d84b4d6827d4")


class ContentTests(unittest.TestCase):
    def test_unused_dlc_catalog_adds_no_requirement(self):
        catalog = ContentCatalog().load_builtin("rise_from_ruin").load_builtin("silver_seas")
        self.assertEqual(len(catalog.keys()), 5)
        p = project(); p.add_trigger(Trigger("log", [events.new_turn()], [actions.log("hello")]))
        plan = p.plan(game_version="2.3.0")
        self.assertEqual(plan["compatibility"]["required_dlc"], [])
        self.assertEqual(plan["dependencies"], [])

    def test_missing_used_dlc_warns_and_still_builds_in_memory(self):
        catalog = ContentCatalog().load_builtin("rise_from_ruin")
        p = project(); p.add_trigger(Trigger("apply", [events.new_turn()], [
            actions.add_transformation(race=races.of_player(players.triggering()),
                                       transformation=catalog.ref("rise_from_ruin.fractured_transformation"))]))
        with tempfile.TemporaryDirectory() as folder:
            plan = p.plan(game_version="2.3.0", game_dir=Path(folder))
        self.assertEqual(plan["dependencies"], ["FRACTURED_RESEARCH.RPK"])
        report = plan["compatibility"]
        self.assertEqual([d["key"] for d in report["required_dlc"]], ["rise_from_ruin"])
        self.assertIn("DLC_FILES_MISSING", {w["code"] for w in report["warnings"]})

    def test_new_dlc_definition_requires_no_core_edit(self):
        data = {"format_version": 1, "dlc": {"key": "future", "title": "Future DLC",
                "content_folder": "FutureDlc", "minimum_game_version": "2.4.0"},
                "resources": [{"key": "future.example", "kind": "side_property", "id": "ABCD000000000001",
                               "name": "Example property", "url": "[#ABCD000000000001]0\\0", "pack": "Future.rpk"}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "future.json"; path.write_text(json.dumps(data), encoding="utf-8")
            catalog = ContentCatalog().load(path)
        p = project(); p.add_trigger(Trigger("future", [events.new_turn()], [
            actions.add_property(player=players.triggering(), property=catalog.ref("future.example"))]))
        report = p.plan(game_version="2.3.0")["compatibility"]
        codes = {w["code"] for w in report["warnings"]}
        self.assertIn("DLC_NEWER_THAN_TARGET", codes)
        self.assertIn("GAME_TOO_OLD_FOR_DLC", codes)

    def test_unknown_catalog_version_and_duplicate_keys_fail(self):
        catalog = ContentCatalog().load_builtin("silver_seas")
        with self.assertRaises(ValidationError):
            catalog.load_builtin("silver_seas")
        with self.assertRaises(ValidationError):
            catalog.load_builtin("../silver_seas")

    def test_known_wrong_resource_kind_is_rejected(self):
        catalog = ContentCatalog().load_builtin("rise_from_ruin")
        with self.assertRaisesRegex(ValidationError, "needs racial_transformation"):
            actions.add_transformation(race=races.of_player(players.triggering()),
                                       transformation=catalog.ref("rise_from_ruin.fractured_unlock"))

    def test_outside_23_series_warns(self):
        p = project(); p.add_trigger(Trigger("log", [events.new_turn()], [actions.log("x")]))
        self.assertIn("OUTSIDE_TARGET_SERIES", {w["code"] for w in p.plan(game_version="2.4.0")["compatibility"]["warnings"]})
