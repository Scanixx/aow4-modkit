from dataclasses import replace
import unittest
from uuid import UUID

from aow4modkit import (ModProject, Trigger, SideProperty, TagBook, TagDefinition,
                       HiddenArtifactMarker, LocalizedText, actions, events, players,
                       variables, ValidationError)
from aow4modkit.formats.rpk import ResourcePack
from aow4modkit.formats.binary import FieldTable


def project():
    return ModProject("Resource test", "ResourceTest", "0.1", "Tester",
                      "c22991fd-bef7-43b1-9bda-d7652112963b")


class ResourceTests(unittest.TestCase):
    def test_pinned_ids_names_order_and_forward_links(self):
        p = project()
        p.pack_name, p.catalog_name = "PINNED_PACK.RPK", "PINNED_TEXT.MO"
        p.definition_order = ("trigger", "marker")
        p.add_resource(SideProperty(key="marker", name="Existing Marker", resource_id=42))
        p.add_trigger(Trigger("trigger", [events.new_turn()], [actions.add_property(
            player=players.triggering(), property=p.ref("marker"))], resource_id=43, name="Existing Trigger"))
        plan = p.plan()
        records = [r for *_, r in ResourcePack.read(plan["files"]["Packs/pinned_pack.rpk"]).records()]
        self.assertEqual([(r.resource_id, r.name) for r in records], [(43, "Existing Trigger"), (42, "Existing Marker")])
        self.assertEqual(plan["dependencies"], [])  # own pack is not an external dependency

    def test_missing_owned_reference_and_wrong_resolved_kind_fail(self):
        p = project()
        p.add_trigger(Trigger("t", [events.new_turn()], [actions.add_property(
            player=players.triggering(), property=p.ref("missing"))]))
        with self.assertRaisesRegex(ValidationError, "Unresolved"):
            p.plan()
        p = project(); p.add_resource(SideProperty(key="property"))
        p.add_trigger(Trigger("t", [events.new_turn()], [actions.give_token(
            player=players.triggering(), token=p.ref("property"))]))
        with self.assertRaisesRegex(ValidationError, "needs token"):
            p.plan()

    def test_hidden_marker_has_no_grants_and_rejects_forged_tag(self):
        p = project()
        book = TagBook(key="book", root="Example", root_guid=UUID(int=1),
                       tags=(TagDefinition("Eligible", UUID(int=2)),))
        p.add_resource(book)
        text = LocalizedText("EXAMPLE@MARKER")
        marker = HiddenArtifactMarker(key="marker", title=text, description=text,
                                      lore=text, forge_description=text, tags=(book.tag("Eligible"),))
        p.add_resource(marker)
        plan = p.plan(); records = [r for *_, r in ResourcePack.read(plan["files"]["Packs/resourcetest.rpk"]).records()]
        fields = records[1].class_fields().fields
        self.assertEqual(fields[10], b"\0")
        self.assertEqual(fields[13], b"\0")
        self.assertEqual(fields[20], b"\0")
        self.assertEqual(fields[21], b"\0")
        p.resources[1] = replace(marker, tags=(replace(book.tag("Eligible"), guid=UUID(int=999)),))
        with self.assertRaisesRegex(ValidationError, "not declared"):
            p.plan()

    def test_duplicate_pinned_ids_fail(self):
        p = project()
        p.add_resource(SideProperty(key="a", resource_id=7))
        p.add_resource(SideProperty(key="b", resource_id=7))
        with self.assertRaisesRegex(ValidationError, "Duplicate owned"):
            p.plan()

    def test_definition_order_must_cover_every_definition(self):
        p = project(); p.add_resource(SideProperty(key="a")); p.definition_order=("other",)
        with self.assertRaisesRegex(ValidationError, "definition_order"):
            p.plan()

    def test_public_loop_and_persistent_variable_recipe(self):
        p = project(); player = players.iterator(); pool = variables.player_pool(player)
        p.add_trigger(Trigger("loop", [events.new_turn()], [actions.for_each_player(
            actions.guard([players.is_valid(player), variables.exists(pool, "DONE").equals(False)], then=[
                variables.set_integer(pool, "DONE", 1)]))], once=False))
        self.assertTrue(p.plan()["files"])
