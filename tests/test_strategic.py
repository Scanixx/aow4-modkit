from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from uuid import UUID

from aow4modkit import (
    ModProject, Trigger, Script, SideProperty, LocalizedText, StoryEvent,
    DialogChoice, PreservedParameter, invoke, sequence, ListKind, actions,
    events, players, variables, localized_link, ValidationError, DEFAULT_PROFILE,
)
from aow4modkit.compiler import TriggerCompiler
from aow4modkit.formats.binary import FieldTable, U32, encode_string
from aow4modkit.formats.rpk import ResourceRecord, ResourcePack
from aow4modkit.resources import ResourceContext

MOD_ID = UUID("3fbd2a36-1a3a-4381-b695-b1fe7b44cfaa")


def project():
    p = ModProject("Strategic test", "StrategicTest", "0.1", "Tester", MOD_ID)
    p.add_resource(SideProperty(key="marker"))
    return p


def children(raw):
    return [ResourceRecord.read(v) for v in FieldTable.read(FieldTable.read(
        FieldTable.read(raw).fields[0]).fields[1]).fields.values()]


class StrategicTests(unittest.TestCase):
    def test_invoke_accepts_native_name_argument_and_checks_types(self):
        pool = variables.player_pool(players.triggering())
        value = invoke("variables.exists", name=variables.name("DONE"), pool=pool)
        self.assertEqual(value.arguments[0], pool)
        with self.assertRaises(ValidationError):
            invoke("variables.exists", name="DONE", pool=pool)
        with self.assertRaises(ValidationError):
            invoke("variables.exists", pool=pool)

    def test_setup_phase_emits_distinct_native_type_in_nested_branch(self):
        pool = variables.player_pool(players.triggering())
        assignment = variables.set_integer(pool, "DONE", 1)
        definition = Script("init", [], [], setups=[actions.when(
            variables.exists(pool, "DONE").equals(False), then=[assignment])])
        compiler = TriggerCompiler(MOD_ID, 123)
        settings = FieldTable.read(FieldTable.read(compiler.compile_script(definition)).fields[0x47432E])
        setup_list = FieldTable.read(settings.fields[14])
        branch = children(setup_list.fields[20])[0]
        self.assertEqual(branch.table.fields[5], U32.pack(2))
        then = children(branch.table.fields[2])[1]
        self.assertEqual(then.table.fields[21], U32.pack(ListKind.SETUPS))
        assigned = children(then.table.fields[20])[0]
        self.assertEqual(assigned.table.fields[5], U32.pack(2))
        with self.assertRaisesRegex(ValidationError, "setup counterparts"):
            compiler.compile_script(Script("bad", [], [], setups=[actions.log("no setup equivalent")]))

    def test_embedded_script_cannot_be_registered_as_global_trigger(self):
        p = project(); p.add_trigger(Script("embedded", [], []))
        with self.assertRaisesRegex(ValidationError, "global Trigger"):
            p.plan()

    def test_localized_link_preserves_direct_and_wrapped_context(self):
        context = ResourceContext({}, DEFAULT_PROFILE)
        inner = FieldTable({1: encode_string("OLD"), 2: b"formatter"}).write()
        wrapped = FieldTable({0: inner, 1: b"flag"}).write()
        value = context.localized(LocalizedText("NEW", wrapped))
        fields = FieldTable.read(value).fields
        self.assertEqual(fields[1], b"flag")
        self.assertEqual(FieldTable.read(fields[0]).fields,
                         {1: encode_string("NEW"), 2: b"formatter"})
        expr = localized_link(LocalizedText("NOTICE", inner))
        node = TriggerCompiler(MOD_ID, 42).expression(expr)
        preset = children(node.table.fields[2])[0]
        self.assertEqual(preset.class_id, 0x4778C0)
        data = FieldTable.read(preset.table.fields[0x4778C0]).fields[0]
        self.assertEqual(FieldTable.read(data).fields[2], b"formatter")

    def test_choices_keep_list_ids_and_share_one_node_identity_sequence(self):
        p = project(); script = Script("empty", [], [])
        # A minimal event uses supported fields; links point to an owned marker.
        params = dict(event_type=p.ref("marker"), initialization=script, rarity=6,
                      pace=1, weight_filter=1, pacing_gate=1,
                      choices=(DialogChoice(0, LocalizedText("CHOICE"), p.ref("marker"), script, script),),
                      native_event_flag_8=False, title=LocalizedText("TITLE"),
                      description=LocalizedText("BODY"), native_event_flag_27=False,
                      native_event_flag_28=False)
        event = StoryEvent(key="event", parameters=params)
        p.add_resource(event)
        payload = p.plan()["files"]["Packs/strategictest.rpk"]
        record = list(ResourcePack.read(payload).records())[-1][-1]
        init = record.class_fields(0x4774F0).fields[1]
        holder = FieldTable.read(record.class_fields(0x474393).fields[4])
        rows = FieldTable.read(FieldTable.read(holder.fields[1]).fields[1])
        button = ResourceRecord.read(rows.fields[0]).table.fields
        identities = []
        for raw in [init, button[2], button[6]]:
            settings = FieldTable.read(FieldTable.read(raw).fields[0x47432E])
            for field in [11, 12, 13, 14]:
                node = FieldTable.read(settings.fields[field])
                identities.append(FieldTable.read(node.fields[7]).fields[10])
        self.assertEqual(len(set(identities)), 12)
        p.resources[-1] = replace(event, parameters={**params, "choices": params["choices"] * 2})
        with self.assertRaisesRegex(ValidationError, "unique list IDs"):
            p.plan()
        p.resources[-1] = replace(event, parameters={**params, "choices": (object(),)})
        with self.assertRaisesRegex(ValidationError, "DialogChoice"):
            p.plan()

    def test_preserved_parameters_require_an_explicit_description(self):
        with self.assertRaises(ValidationError):
            PreservedParameter(b"static", "")
        with self.assertRaises(ValidationError):
            PreservedParameter("not bytes", "Explanation")

    def test_asset_paths_and_filename_case_collision_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            asset = Path(folder) / "asset.bin"; asset.write_bytes(b"owned")
            for relative in ["../outside", "./alias", "folder//alias", "C:/absolute", "folder\\alias", "STRATEGICTEST.ACP"]:
                p = project(); p.assets = {relative: asset}
                with self.subTest(path=relative), self.assertRaises(ValidationError):
                    p.plan()
            p = project(); p.assets = {"Libraries/OWN.CLB": asset}
            self.assertEqual(p.plan()["files"]["Libraries/OWN.CLB"], b"owned")

    def test_explicit_dependency_order_and_filename_case_are_preserved(self):
        p = project(); p.pack_name = "CUSTOM.RPK"; p.pack_filename = "CUSTOM.rpk"
        p.catalog_name = "TEXT.MO"; p.catalog_filename = "TEXT.mo"
        p.messages = {"TITLE": "Title"}
        p.dependency_manifest = ("SECOND.RPK", "TEXT.MO", "FIRST.RPK")
        plan = p.plan()
        self.assertEqual(plan["dependencies"], list(p.dependency_manifest))
        self.assertIn("Packs/CUSTOM.rpk", plan["files"])
        self.assertIn("Language/TEXT.mo", plan["files"])
        p.dependency_manifest = ("TEXT.MO", "TEXT.MO")
        with self.assertRaises(ValidationError):
            p.plan()

    def test_references_in_global_setup_are_validated(self):
        p = project()
        # Use a reference in an unsupported/missing grant; plan must catch it
        # even though a later setup serializer check would reject the action.
        p.add_trigger(Trigger("setup_ref", [events.new_turn()], [], setups=[actions.add_property(
            player=players.triggering(), property=p.ref("missing"))]))
        with self.assertRaisesRegex(ValidationError, "Unresolved"):
            p.plan()
