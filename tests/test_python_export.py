"""Synthetic source-export tests: no real mod/game files are distributed."""
import ast
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from uuid import UUID

from aow4modkit import (ModProject, Trigger, Script, SideProperty, StoryEvent, DialogChoice,
                       LocalizedText, ResourceLink, ResourceRef, actions, events, players,
                       variables, core, invoke, localized_link, ValidationError)
from aow4modkit.analysis import (decode_pack, export_trigger_python, rebuild_trigger_pack,
                               rebuild_export, compare_trigger_packs)
from aow4modkit.cli import main
from aow4modkit.constants import ClassId as C
from aow4modkit.formats.binary import FieldTable, U32
from aow4modkit.formats.rpk import ResourcePack, ResourceRecord
from test_analysis import packed, record, change_record, rows, parse_rows

MOD_ID = UUID(int=1)


def builder(directory):
    return runpy.run_path(str(directory / "triggers.py"))["build_triggers"]()


def dialog_pack():
    p = ModProject("Dialog fixture", "DialogFixture", "0.1", "Tester", MOD_ID)
    p.add_resource(SideProperty(key="category"))
    initial = Script("init", [], [], setups=[variables.set_integer(
        variables.player_pool(players.triggering()), "READY", 1)])
    action = Script("action", [], [actions.log("Chosen")], once=True)
    visible = Script("visible", [], [], conditions=[players.is_valid(players.triggering())], once=False)
    choices = tuple(DialogChoice(i, LocalizedText(f"CHOICE@{i}"), p.ref("category"), action, visible)
                    for i in (5, 9))
    p.add_resource(StoryEvent(key="dialog", parameters=dict(
        event_type=p.ref("category"), initialization=initial, rarity=6, pace=1,
        weight_filter=1, pacing_gate=1, choices=choices, native_event_flag_8=False,
        title=LocalizedText("TITLE"), description=LocalizedText("BODY"),
        native_event_flag_27=False, native_event_flag_28=False)))
    return p.plan()["files"]["Packs/dialogfixture.rpk"]


class PythonExportTests(unittest.TestCase):
    def test_export_never_executes_input_text_and_rebuild_is_equivalent(self):
        text = "__import__('os').system('THIS IS DATA')\nλ 'quoted'"
        raw = packed(record(Trigger("data", [events.new_turn()], [actions.log(text)])))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"source"
            manifest = export_trigger_python(decode_pack(raw), target, mod_id=MOD_ID)
            self.assertEqual(manifest["equivalence_status"], "not yet rebuilt")
            for path in target.rglob("*.py"):
                ast.parse(path.read_text())
            report = rebuild_export(target, Path(folder)/"rebuilt.rpk")
            self.assertTrue(report["equivalent"])
            decoded = decode_pack((Path(folder)/"rebuilt.rpk").read_bytes())
            self.assertIn(text, [n["value"] for n in decoded.to_dict()["nodes"] if n["kind"] == "preset"])

    def test_generated_definitions_do_not_read_the_input_template(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            export_trigger_python(decode_pack(packed()), target)
            (target/"input.rpk").unlink()
            definitions = builder(target)
            self.assertEqual(len(definitions), 1)
            self.assertIsInstance(next(iter(definitions.values())), Trigger)
            source = next((target/"scripts").glob("*.py")).read_text()
            self.assertIn("invoke", source)
            self.assertNotIn("read_pack", source)
            self.assertNotIn("ResourcePack", source)

    def test_original_uuid_must_be_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"source"
            export_trigger_python(decode_pack(packed()), target)
            with self.assertRaisesRegex(ValidationError, "UUID"):
                rebuild_export(target, Path(folder)/"rebuilt.rpk")
            report = rebuild_export(target, Path(folder)/"rebuilt.rpk", mod_id=MOD_ID)
            self.assertTrue(report["equivalent"])

    def test_strict_export_rejects_unknown_disabled_and_extra_fields(self):
        edits = [lambda n: n.table.fields.update({1: U32.pack(99999)}),
                 lambda n: n.table.fields.update({3: b"\x00"}),
                 lambda n: n.table.fields.update({9000: b"future"}),
                 lambda n: n.table.fields.update({0: U32.pack(9)})]
        for edit in edits:
            with tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/"source"
                with self.assertRaises(ValidationError):
                    export_trigger_python(decode_pack(packed(change_record(edit))), target)
                self.assertFalse(target.exists())

    def test_strict_export_rejects_noncanonical_argument_rows(self):
        def edit(node):
            args = parse_rows(node.table.fields[2])
            node.table.fields[2] = FieldTable({0: FieldTable({1: FieldTable({
                99: args[0].write()}).write()}).write()}).write()
        decoded = decode_pack(packed(change_record(edit)))
        self.assertFalse(decoded.diagnostics)
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValidationError, "row indices"):
            export_trigger_python(decoded, Path(folder)/"source")

    def test_native_greater_comparison_and_alias_are_preserved(self):
        item = record(Trigger("greater", [events.new_turn()], [], conditions=[core.current_round().equals(1)]))
        holder = item.class_fields(); script = FieldTable.read(holder.fields[0])
        settings = FieldTable.read(script.fields[C.TRIGGER_SETTINGS]); root = FieldTable.read(settings.fields[12])
        condition = parse_rows(root.fields[20])[0]; args = parse_rows(condition.table.fields[2])
        args[1].table.fields[20] = U32.pack(10)
        condition.table.fields[2] = rows(args); root.fields[20] = rows([condition])
        settings.fields[12] = root.write(); script.fields[C.TRIGGER_SETTINGS] = settings.write()
        holder.fields[0] = script.write(); item.table.fields[C.TRIGGER] = holder.write()
        raw = packed(item)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder); export_trigger_python(decode_pack(raw), target, mod_id=MOD_ID)
            self.assertIn("ComparisonOperator.GREATER", next((target/"scripts").glob("*.py")).read_text())
            rebuilt = rebuild_trigger_pack(raw, builder(target), mod_id=MOD_ID)
            self.assertTrue(compare_trigger_packs(raw, rebuilt)["equivalent"])

    def test_story_event_scripts_setup_and_choice_ids_are_preserved(self):
        raw = dialog_pack()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder); export_trigger_python(decode_pack(raw), target, mod_id=MOD_ID)
            rebuilt = rebuild_trigger_pack(raw, builder(target), mod_id=MOD_ID)
            report = compare_trigger_packs(raw, rebuilt)
            self.assertTrue(report["equivalent"])
            decoded = decode_pack(rebuilt)
            self.assertEqual([s.choice["list_id"] for s in decoded.scripts[1:]], [5, 5, 9, 9])
            self.assertTrue(all(s.context == 2 for s in decoded.scripts))
            self.assertEqual(decoded.scripts[0].phases["setups"].children[0].data_type, 2)

    def test_edited_source_requires_allow_changes_and_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"source"; output = Path(folder)/"rebuilt.rpk"
            export_trigger_python(decode_pack(packed()), target, mod_id=MOD_ID)
            path = next((target/"scripts").glob("*.py"))
            path.write_text(path.read_text().replace("Hello", "Changed"), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "differ"):
                rebuild_export(target, output)
            self.assertFalse(output.exists())
            report = rebuild_export(target, output, allow_changes=True)
            self.assertFalse(report["equivalent"])
            self.assertTrue(report["nonscript_envelope_equal"])
            self.assertEqual(len(report["differing_scripts"]), 1)

    def test_unknown_nonscript_resource_bytes_are_not_reconstructed(self):
        other = ResourceRecord.create(0x12345678, 99, "Unknown", 1, {0x12345678: b"opaque\x00\xff"})
        raw = ResourcePack.create("TEST.RPK", [record(), other]).write()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder); export_trigger_python(decode_pack(raw), target, mod_id=MOD_ID)
            rebuilt = rebuild_trigger_pack(raw, builder(target), mod_id=MOD_ID)
            after = list(ResourcePack.read(rebuilt).records())[1][-1]
            self.assertEqual(after.write(), other.write())
            self.assertTrue(compare_trigger_packs(raw, rebuilt)["nonscript_envelope_equal"])

    def test_resource_link_has_no_fabricated_pack_origin(self):
        link = ResourceLink(999, "External", "[#00000000000003E7]0\\0")
        p = ModProject("Links", "Links", "0.1", "Tester", MOD_ID)
        p.add_trigger(Trigger("links", [events.new_turn()], [actions.add_property(player=players.triggering(), property=link)]))
        with self.assertRaisesRegex(ValidationError, "origin pack"):
            p.plan()
        ref = ResourceRef(999, "External", link.url, "EXAMPLE.RPK")
        self.assertEqual(ref.pack, "EXAMPLE.RPK")

    def test_exact_external_url_is_preserved(self):
        link = ResourceLink(999, "External", "[#00000000000003E7]7\\14")
        raw = packed(record(Trigger("links", [events.new_turn()], [actions.add_property(
            player=players.triggering(), property=link)])))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder); export_trigger_python(decode_pack(raw), target, mod_id=MOD_ID)
            self.assertTrue(compare_trigger_packs(raw, rebuild_trigger_pack(raw, builder(target), mod_id=MOD_ID))["equivalent"])
            rows_data = json.loads((target/"resource-links.json").read_text())
            self.assertFalse(any("pack" in row for row in rows_data.values()))
            self.assertIn(link.url, [row["url"] for row in rows_data.values()])

    def test_localized_notification_formatter_is_preserved(self):
        from aow4modkit import TextContext, TextSubstitution
        icon = ResourceLink(999, "Icon", "[#00000000000003E7]0\\0")
        context = TextContext(substitutions=(TextSubstitution('{example}','synthetic formatter'),))
        message = localized_link(LocalizedText("EXAMPLE@NOTICE", context))
        notification = invoke("players.show_todo_event_at_position", player=players.triggering(),
            title=message, body=message, icon=icon, hover_icon=icon,
            position=invoke("positions.special_operation", special_operation=invoke("spells.triggering")),
            variables=invoke("pools.local"))
        raw = packed(record(Trigger("notice", [events.new_turn()], [notification])))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder); export_trigger_python(decode_pack(raw), target, mod_id=MOD_ID)
            rebuilt = rebuild_trigger_pack(raw, builder(target), mod_id=MOD_ID)
            self.assertTrue(compare_trigger_packs(raw, rebuilt)["equivalent"])
            texts = json.loads((target/"localized-links.json").read_text())
            self.assertEqual(len(texts), 1)
            self.assertEqual(next(iter(texts.values()))['substitutions'],[dict(token='{example}',value='synthetic formatter')])
            self.assertNotIn('context_hex',next(iter(texts.values())))
            self.assertIn('TextSubstitution(', (target/'localized_texts.py').read_text())

    def test_missing_definitions_and_wrong_trigger_kind_are_rejected(self):
        raw = packed()
        with self.assertRaisesRegex(ValidationError, "every registered"):
            rebuild_trigger_pack(raw, {}, mod_id=MOD_ID)
        decoded = decode_pack(raw)
        with self.assertRaisesRegex(ValidationError, "kind"):
            rebuild_trigger_pack(raw, {decoded.scripts[0].path: Script("bad", [], [])}, mod_id=MOD_ID)

    def test_existing_source_and_rebuild_outputs_are_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"source"; output = Path(folder)/"rebuilt.rpk"
            export_trigger_python(decode_pack(packed()), target, mod_id=MOD_ID)
            with self.assertRaises(ValidationError):
                export_trigger_python(decode_pack(packed()), target)
            output.write_bytes(b"user data")
            with self.assertRaises(ValidationError):
                rebuild_export(target, output)
            self.assertEqual(output.read_bytes(), b"user data")

    def test_rebuild_is_reproducible_and_template_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"source"; output = Path(folder)/"rebuilt.rpk"
            export_trigger_python(decode_pack(packed()), target, mod_id=MOD_ID)
            rebuild_export(target, output); before = output.read_bytes()
            rebuild_export(target, output); self.assertEqual(output.read_bytes(), before)
            (target/"input.rpk").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValidationError, "template"):
                rebuild_export(target, output)

    def test_cli_exports_then_explicitly_rebuilds(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); source = root/"input.rpk"; source.write_bytes(packed())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["export-python", str(source), "--output", str(root/"export"), "--mod-id", str(MOD_ID)]), 0)
                self.assertEqual(main(["rebuild-triggers", str(root/"export"), "--output", str(root/"rebuilt.rpk")]), 0)
            self.assertTrue((root/"rebuilt.verification.json").is_file())

    def test_unknown_diagnostics_cannot_be_claimed_equivalent(self):
        raw = packed(change_record(lambda n: n.table.fields.update({9000: b"unknown"})))
        self.assertFalse(compare_trigger_packs(raw, raw)["equivalent"])
