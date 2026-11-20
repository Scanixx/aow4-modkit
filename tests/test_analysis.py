from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from uuid import UUID

from aow4modkit import (Trigger, Script, actions, events, variables, players,
                       invoke, sequence, ListKind, LocalizedText, localized_link,
                       ResourceRef, ValidationError, FormatError)
from aow4modkit.analysis import (DecodeLimits, decode_pack, read_pack, render_report,
                               render_script, walk_nodes, write_analysis)
from aow4modkit.cli import main, inspect_file
from aow4modkit.compiler import TriggerCompiler
from aow4modkit.constants import ClassId as C
from aow4modkit.formats.binary import FieldTable, U32, encode_string
from aow4modkit.formats.rpk import ResourcePack, ResourceRecord


def rows(records):
    return FieldTable({0: FieldTable({1: FieldTable({
        i: record.write() for i, record in enumerate(records)}).write()}).write()}).write()


def parse_rows(raw):
    fields = FieldTable.read(FieldTable.read(FieldTable.read(raw).fields[0]).fields[1]).fields
    return [ResourceRecord.read(value) for value in fields.values()]


def record(trigger=None):
    trigger = trigger or Trigger("hello", [events.new_turn()], [actions.log("Hello 'world'\nλ")])
    return TriggerCompiler(UUID(int=1), 42).compile(trigger, resource_id=42, index=0)


def packed(item=None):
    return ResourcePack.create("TEST.RPK", [item or record()]).write()


def change_record(edit=None, settings_edit=None):
    result = record()
    wrapper = result.class_fields()
    script = FieldTable.read(wrapper.fields[0])
    settings = FieldTable.read(script.fields[C.TRIGGER_SETTINGS])
    if settings_edit:
        settings_edit(settings)
    if edit:
        root = FieldTable.read(settings.fields[13])
        records = parse_rows(root.fields[20])
        edit(records[0])
        root.fields[20] = rows(records)
        settings.fields[13] = root.write()
    script.fields[C.TRIGGER_SETTINGS] = settings.write()
    wrapper.fields[0] = script.write()
    result.table.fields[C.TRIGGER] = wrapper.write()
    return result


class AnalysisTests(unittest.TestCase):
    def test_decodes_native_signatures_literals_and_provenance(self):
        raw = packed(); result = decode_pack(raw, source_name="folder/example.rpk")
        self.assertEqual(result.source_name, "example.rpk")
        self.assertEqual(result.statistics["scripts"], 1)
        self.assertEqual(result.statistics["unknown_nodes"], 0)
        self.assertFalse(result.diagnostics)
        nodes = [n for root in result.scripts[0].phases.values() for n in walk_nodes(root)]
        self.assertIn("literal.string", [n.function_name for n in nodes])
        self.assertIn("actions.log", [n.function_name for n in nodes])
        self.assertIn("Hello 'world'\nλ", [n.value for n in nodes if n.kind == "preset"])
        for node in nodes:
            for origin in node.fields.values():
                data = result.source_bytes(origin.span)
                self.assertEqual(hashlib.sha256(data).hexdigest(), origin.sha256)
                self.assertEqual(len(data), origin.size)
        view = result.to_dict()
        self.assertEqual(view["node_representation"], "flat-v1")
        self.assertEqual(len(view["nodes"]), len(nodes))
        self.assertEqual(len({n["node_id"] for n in view["nodes"]}), len(nodes))
        self.assertNotIn("_input_bytes", view)
        json.dumps(view)

    def test_unknown_function_preserves_children_and_source(self):
        value = change_record(lambda node: node.table.fields.update({1: U32.pack(9999)}))
        result = decode_pack(packed(value))
        root = result.scripts[0].phases["actions"].children[0]
        self.assertIsNone(root.function_name)
        self.assertEqual(root.function_id, 9999)
        self.assertEqual(len(root.children), 1)
        self.assertEqual(result.statistics["unknown_nodes"], 1)
        self.assertIn("UNKNOWN_FUNCTION", [d.code for d in result.diagnostics])
        self.assertIn("UNKNOWN_FUNCTION[3:9999]", render_script(result.scripts[0]))

    def test_unknown_class_does_not_guess_child_or_identity_layout(self):
        def edit(node):
            node.class_id = 0xDEADBEEF
            node.table.fields[2] = b"not a child store"
            node.table.fields[7] = b"not an identity table"
        result = decode_pack(packed(change_record(edit)))
        node = result.scripts[0].phases["actions"].children[0]
        self.assertEqual(node.kind, "unknown")
        self.assertFalse(node.children)
        self.assertEqual(result.source_bytes(node.fields[2].span), b"not a child store")
        self.assertIn("UNKNOWN_NODE_CLASS", [d.code for d in result.diagnostics])

    def test_disabled_nodes_and_script_flags_remain_visible(self):
        item = change_record(lambda node: node.table.fields.update({3: b"\x00"}),
                             lambda settings: settings.fields.update({2: b"\x00", 3: b"\x00", 4: b"\x00"}))
        result = decode_pack(packed(item)); script = result.scripts[0]
        self.assertEqual((script.once, script.enabled, script.active), (False, False, False))
        self.assertEqual(result.statistics["disabled_nodes"], 1)
        self.assertIn("[DISABLED]", render_script(script))

    def test_unknown_fields_have_raw_byte_access_and_diagnostics(self):
        raw_value = b"unknown value \x00\xff"
        result = decode_pack(packed(change_record(lambda n: n.table.fields.update({9001: raw_value}))))
        node = result.scripts[0].phases["actions"].children[0]
        self.assertEqual(node.unknown_fields, (9001,))
        self.assertEqual(result.source_bytes(node.fields[9001].span), raw_value)
        self.assertIn("UNKNOWN_NODE_FIELDS", [d.code for d in result.diagnostics])

    def test_duplicate_argument_slots_are_reported_not_overwritten(self):
        def edit(node):
            args = parse_rows(node.table.fields[2])
            node.table.fields[2] = rows(args+args)
        result = decode_pack(packed(change_record(edit)))
        self.assertEqual(len(result.scripts[0].phases["actions"].children[0].children), 2)
        self.assertIn("DUPLICATE_ARGUMENT_SLOT", [d.code for d in result.diagnostics])
        self.assertGreater(result.statistics["errors"], 0)

    def test_argument_type_mismatch_has_exact_origin(self):
        def edit(node):
            args = parse_rows(node.table.fields[2])
            args[0].table.fields[5] = U32.pack(12)
            node.table.fields[2] = rows(args)
        result = decode_pack(packed(change_record(edit)))
        error = next(d for d in result.diagnostics if d.code == "ARGUMENT_TYPE_MISMATCH")
        self.assertIn("argument[0]", error.path)
        self.assertIsNotNone(error.span)

    def test_unknown_script_field_and_context_are_reported(self):
        item = change_record(settings_edit=lambda n: n.fields.update({999: b"future", 0: U32.pack(9)}))
        result = decode_pack(packed(item))
        self.assertEqual(result.scripts[0].context, 9)
        self.assertIn("UNKNOWN_SCRIPT_FIELDS", [d.code for d in result.diagnostics])
        self.assertIn("UNEXPECTED_SCRIPT_CONTEXT", [d.code for d in result.diagnostics])

    def test_setup_counterparts_keep_native_type(self):
        setup = variables.set_integer(variables.player_pool(players.triggering()), "DONE", 1)
        trigger = Trigger("init", [events.new_turn()], [], setups=[setup])
        result = decode_pack(packed(record(trigger)))
        node = result.scripts[0].phases["setups"].children[0]
        self.assertEqual((node.data_type, node.function_id, node.function_name), (2, 6, "variables.set"))
        self.assertIn("[native setup]", render_script(result.scripts[0]))

    def test_comparison_alias_is_deterministic(self):
        trigger = Trigger("compare", [events.new_turn()], [], conditions=[players.is_ai(players.triggering()).equals(False)])
        result = decode_pack(packed(record(trigger)))
        self.assertEqual(result.scripts[0].phases["conditions"].children[0].function_name, "conditions.boolean_equals")
        from aow4modkit import core
        trigger = replace(trigger, conditions=[core.current_round().equals(1)])
        result = decode_pack(packed(record(trigger)))
        node = result.scripts[0].phases["conditions"].children[0]
        self.assertEqual(node.function_name, "comparisons.integer")
        self.assertEqual(node.aliases, ("conditions.integer_equals",))

    def test_localized_notification_and_external_reference_are_data(self):
        reference = ResourceRef(999, "External", "[#00000000000003E7]0\\0", "EXAMPLE.RPK")
        trigger = Trigger("links", [events.new_turn()], [actions.add_property(player=players.triggering(), property=reference)])
        result = decode_pack(packed(record(trigger)))
        self.assertEqual(result.references[0]["resource_id"], "00000000000003E7")
        self.assertEqual(result.references[0]["scope"], "external_origin_unresolved")
        compiler = TriggerCompiler(UUID(int=1), 42)
        node = compiler.expression(localized_link(LocalizedText("NOTICE@KEY")))
        trigger = record()
        # A stand-alone localized expression as an action intentionally has an
        # unsupported list type; it is still decoded without executing text.
        wrapper = trigger.class_fields(); script = FieldTable.read(wrapper.fields[0])
        settings = FieldTable.read(script.fields[C.TRIGGER_SETTINGS]); root = FieldTable.read(settings.fields[13])
        root.fields[20] = rows([node]); settings.fields[13] = root.write()
        script.fields[C.TRIGGER_SETTINGS] = settings.write(); wrapper.fields[0] = script.write(); trigger.table.fields[C.TRIGGER] = wrapper.write()
        result = decode_pack(packed(trigger))
        value = result.scripts[0].phases["actions"].children[0].children[0].value
        self.assertEqual(value["key"], "NOTICE@KEY")
        self.assertFalse(value["translation_resolved"])

    def test_limits_and_malformed_framing(self):
        raw = packed()
        for limits in [DecodeLimits(max_input_bytes=1), DecodeLimits(max_parsed_bytes=1),
                       DecodeLimits(max_nodes=1), DecodeLimits(max_fields=1), DecodeLimits(max_depth=1)]:
            with self.subTest(limits=limits), self.assertRaises(FormatError):
                decode_pack(raw, limits=limits)
        with self.assertRaises(FormatError):
            decode_pack(raw[:-1])
        with self.assertRaises(ValueError):
            DecodeLimits(max_depth=129)

    def test_native_argument_wrapper_is_not_guessed(self):
        item = change_record(lambda n: n.table.fields.update({2: FieldTable({7: b"opaque"}).write()}))
        with self.assertRaisesRegex(FormatError, "child-store wrapper"):
            decode_pack(packed(item))

    def test_unknown_resource_is_inventory_only(self):
        item = ResourceRecord.create(0x12345678, 77, "Unknown Resource", 0, {0x12345678: b"opaque"})
        result = decode_pack(packed(item))
        self.assertEqual(result.statistics["resources_inventoried_only"], 1)
        self.assertFalse(result.scripts)
        self.assertIn("not a complete mod export", render_report(result))

    def test_story_event_initialization_actions_and_visibility_are_discovered(self):
        from aow4modkit import ModProject, SideProperty, StoryEvent, DialogChoice
        p = ModProject("Dialog fixture", "DialogFixture", "0.1", "Tester", UUID(int=3))
        p.add_resource(SideProperty(key="category"))
        init = Script("init", [], [], setups=[variables.set_integer(
            variables.player_pool(players.triggering()), "READY", 1)])
        action = Script("action", [], [actions.log("Chosen")], once=True)
        visible = Script("visible", [], [], conditions=[players.is_valid(players.triggering())], once=False)
        choices = tuple(DialogChoice(i, LocalizedText(f"CHOICE@{i}"), p.ref("category"), action, visible)
                        for i in (5, 9))
        p.add_resource(StoryEvent(key="dialog", parameters=dict(
            event_type=p.ref("category"), initialization=init, rarity=6, pace=1,
            weight_filter=1, pacing_gate=1, choices=choices, native_event_flag_8=False,
            title=LocalizedText("TITLE"), description=LocalizedText("BODY"),
            native_event_flag_27=False, native_event_flag_28=False)))
        result = decode_pack(p.plan()["files"]["Packs/dialogfixture.rpk"])
        self.assertEqual([s.role for s in result.scripts], ["initialization", "choice[0].action",
            "choice[0].visibility", "choice[1].action", "choice[1].visibility"])
        self.assertEqual([s.choice["list_id"] for s in result.scripts[1:]], [5, 5, 9, 9])
        self.assertTrue(all(s.context == 2 for s in result.scripts))
        self.assertTrue(all(s.choice["next_free_id"] == 10 for s in result.scripts[1:]))
        self.assertEqual(result.statistics["duplicate_node_identities"], 0)
        self.assertFalse(result.diagnostics)

    def test_malformed_scalar_and_phase_kind_have_clear_diagnostics(self):
        item = change_record(lambda n: n.table.fields.update({5: b"\x03"}))
        result = decode_pack(packed(item))
        self.assertIn("INVALID_SCALAR", [d.code for d in result.diagnostics])
        self.assertIn("Diagnostics", render_report(result))
        def settings_edit(settings):
            phase = FieldTable.read(settings.fields[13]); phase.fields[21] = U32.pack(1)
            settings.fields[13] = phase.write()
        result = decode_pack(packed(change_record(settings_edit=settings_edit)))
        self.assertIn("PHASE_KIND_MISMATCH", [d.code for d in result.diagnostics])

    def test_same_resource_links_are_marked_internal_without_a_game_catalog(self):
        reference = ResourceRef(42, "Self", "[#000000000000002A]0\\0", "TEST.RPK")
        trigger = Trigger("links", [events.new_turn()], [actions.add_property(player=players.triggering(), property=reference)])
        decoded = decode_pack(packed(record(trigger)))
        self.assertEqual(decoded.references[0]["scope"], "internal")

    def test_output_manifest_hashes_match_original_and_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            decoded = decode_pack(packed()); write_analysis(decoded, path)
            manifest = json.loads((path / "analysis-manifest.json").read_text())
            self.assertTrue(manifest["analysis_only"])
            for name, digest in manifest["files"].items():
                self.assertEqual(hashlib.sha256((path / name).read_bytes()).hexdigest(), digest)

    def test_analysis_output_is_reproducible_and_user_edits_are_protected(self):
        result = decode_pack(packed())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "analysis"
            write_analysis(result, target)
            before = (target / "decoded.json").read_bytes()
            write_analysis(result, target)
            self.assertEqual((target / "decoded.json").read_bytes(), before)
            self.assertEqual((target / "input.rpk").read_bytes(), packed())
            (target / "report.md").write_text("My notes", encoding="utf-8")
            with self.assertRaises(ValidationError):
                write_analysis(result, target)
            self.assertEqual((target / "report.md").read_text(), "My notes")

    def test_unowned_output_and_other_input_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); (target / "notes.txt").write_text("keep")
            with self.assertRaises(ValidationError):
                write_analysis(decode_pack(packed()), target)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory); write_analysis(decode_pack(packed()), target)
            other = record(Trigger("other", [events.new_turn()], []))
            with self.assertRaises(ValidationError):
                write_analysis(decode_pack(packed(other)), target)

    def test_cli_preserves_existing_inspect_and_adds_detail_and_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); path = base / "example.rpk"; path.write_bytes(packed())
            self.assertNotIn("scripts", inspect_file(path))
            with redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(main(["inspect", str(path), "--detail"]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["statistics"]["scripts"], 1)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["decode", str(path), "--output", str(base/"analysis")]), 0)
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["decode", str(path), "--output", str(base)]), 2)

    def test_cli_reports_semantic_errors_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); path = base / "example.rpk"
            path.write_bytes(packed(change_record(lambda n: n.table.fields.update({3: b"\x09"}))))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["decode", str(path), "--output", str(base/"analysis")]), 3)
            self.assertTrue((base/"analysis/report.md").is_file())

    def test_field_spans_include_buffer_offset_and_preserve_serialization(self):
        raw = b"HEAD" + FieldTable({2: b"ab", 9000: b"xyz"}).write()
        table = FieldTable.read(raw, 4)
        for key, (start, end) in table.field_spans.items():
            self.assertEqual(raw[start:end], table.fields[key])
        self.assertEqual(table.write(), raw[4:])
