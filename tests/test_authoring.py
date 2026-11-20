import unittest

from aow4modkit import ModProject, Trigger, actions, core, events, players, races, ValidationError
from aow4modkit.constants import ClassId, NodeField
from aow4modkit.formats.binary import FieldTable
from aow4modkit.formats.rpk import ResourcePack


def project():
    return ModProject("Example", "Example", "0.1", "Tester", "ddfd7b48-d127-41e2-b366-5f54acc2239a")


class AuthoringTests(unittest.TestCase):
    def test_type_checks_before_serialization(self):
        with self.assertRaisesRegex(ValidationError, "expects PLAYER"):
            players.is_ai(core.current_round())
        with self.assertRaises(ValidationError):
            core.current_round().equals(True)
        with self.assertRaises(TypeError):
            bool(players.is_ai(players.triggering()))

    def test_trigger_rejects_python_conditions(self):
        with self.assertRaises(ValidationError):
            Trigger("bad", [events.new_turn()], [actions.log("x")], conditions=[True])

    def test_named_api_emits_native_log_function(self):
        p = project()
        p.add_trigger(Trigger("first", [events.new_turn()], [actions.log("hello")]))
        plan = p.plan()
        pack = ResourcePack.read(plan["files"]["Packs/example.rpk"])
        record = next(pack.records())[3]
        script = FieldTable.read(record.class_fields().fields[0])
        settings = FieldTable.read(script.fields[ClassId.TRIGGER_SETTINGS])
        action_list = FieldTable.read(settings.fields[13])
        children = FieldTable.read(FieldTable.read(FieldTable.read(action_list.fields[20]).fields[0]).fields[1])
        call = FieldTable.read(children.fields[0], 4)
        self.assertEqual(int.from_bytes(call.fields[NodeField.DATA_TYPE], "little"), 3)
        self.assertEqual(int.from_bytes(call.fields[NodeField.FUNCTION], "little"), 468)

    def test_explicit_guard_branch_is_supported(self):
        p = project()
        player = players.triggering()
        p.add_trigger(Trigger("guard", [events.new_turn()], [
            actions.when(players.is_valid(player), then=[
                actions.when(players.is_ai(player), then=[actions.log("AI")])])]))
        self.assertTrue(p.plan()["files"])

    def test_stable_keys_keep_ids_when_reordered(self):
        a = Trigger("a", [events.new_turn()], [actions.log("a")])
        b = Trigger("b", [events.new_turn()], [actions.log("b")])
        p = project(); p.triggers = [a, b]
        before = {r["key"]: r["id"] for r in p.plan()["resources"]}
        p.triggers.reverse()
        self.assertEqual(before, {r["key"]: r["id"] for r in p.plan()["resources"]})

    def test_duplicate_keys_rejected(self):
        p = project(); trigger = Trigger("same", [events.new_turn()], [actions.log("a")])
        p.triggers = [trigger, trigger]
        with self.assertRaises(ValidationError):
            p.plan()
