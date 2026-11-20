"""Template-free RPK construction/export tested with authored synthetic data."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from aow4modkit import (ResourcePackProject,ResourceHandle,ResourceLink,ModProject,PreservedParameter,
                       SideProperty,SpellUnlockProperty,Trigger,actions,events,ValidationError,EmptyTextContext)
from aow4modkit.analysis import decode_pack,export_pack_python,build_pack_export,compare_resource_packs
from aow4modkit.cli import main
from aow4modkit.formats.binary import FieldTable
from aow4modkit.formats.rpk import ResourcePack,ResourceRecord
from test_python_export import dialog_pack

MOD_ID=UUID(int=1)


def basic_project():
    return ResourcePackProject("TEST.RPK",MOD_ID,(
        SideProperty(key="marker",name="Marker",resource_id=42),
        Trigger("trigger",[events.new_turn()],[actions.log("Hello")],resource_id=43,name="Trigger")),
        dependencies=("Z_LAST.RPK","A_FIRST.RPK"))


class ResourceExportTests(unittest.TestCase):
    def test_complete_pack_builds_without_opening_any_input_rpk(self):
        raw=basic_project().build()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source";output=Path(directory)/"result.rpk"
            manifest=export_pack_python(decode_pack(raw),source,mod_id=MOD_ID)
            self.assertFalse(any(source.rglob("*.rpk")))
            self.assertFalse(manifest["binary_template_required"])
            original_open=Path.open
            def guarded_open(path,*args,**kwargs):
                mode=args[0] if args else kwargs.get("mode","r")
                if path.suffix.lower()==".rpk" and "r" in mode:
                    raise AssertionError("Build attempted to read an RPK input")
                return original_open(path,*args,**kwargs)
            with patch.object(Path,"open",guarded_open):
                report=build_pack_export(source,output)
            self.assertIsNone(report["equivalent"])
            self.assertFalse(report["reference_compared"])
            self.assertTrue(compare_resource_packs(raw,output.read_bytes())["equivalent"])

    def test_dialog_scripts_and_choice_wrappers_construct_without_template(self):
        raw=dialog_pack()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source";output=Path(directory)/"result.rpk"
            export_pack_python(decode_pack(raw),source,mod_id=MOD_ID)
            project=runpy.run_path(str(source/"resources.py"))["build_pack"]()
            self.assertIsInstance(project,ResourcePackProject)
            result=project.build()
            self.assertTrue(compare_resource_packs(raw,result)["equivalent"])
            report=build_pack_export(source,output)
            self.assertEqual(report["resources_built"],2)
            self.assertFalse(report["binary_template_used"])
            decoded=decode_pack(result)
            self.assertEqual([s.choice["list_id"] for s in decoded.scripts[1:]],[5,5,9,9])

    def test_pack_without_any_scripts_is_supported(self):
        raw=ResourcePackProject("TEST.RPK",MOD_ID,(SideProperty(key="p",name="Property",resource_id=42),)).build()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source"
            export_pack_python(decode_pack(raw),source,mod_id=MOD_ID)
            rebuilt=runpy.run_path(str(source/"resources.py"))["build_pack"]().build()
            self.assertTrue(compare_resource_packs(raw,rebuilt)["equivalent"])

    def test_lightweight_handle_and_explicit_dependency_order(self):
        definitions=(SpellUnlockProperty(key="unlock",name="Unlock",resource_id=42,parameters=dict(
            empty_title=EmptyTextContext(),
            empty_description=EmptyTextContext(),
            native_unlock_flag_3=False,operations=(ResourceHandle(99,"External operation"),))),)
        project=ResourcePackProject("TEST.RPK",MOD_ID,definitions,dependencies=("Z.RPK","A.RPK"))
        raw=project.build();self.assertEqual(ResourcePack.read(raw).dependencies,["Z.RPK","A.RPK"])
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source"
            export_pack_python(decode_pack(raw),source,mod_id=MOD_ID)
            rebuilt=runpy.run_path(str(source/"resources.py"))["build_pack"]().build()
            self.assertTrue(compare_resource_packs(raw,rebuilt)["equivalent"])
        mod=ModProject("Test","Test","0.1","Tester",MOD_ID)
        mod.add_resource(definitions[0])
        with self.assertRaises(ValidationError):mod.plan()

    def test_unknown_resource_is_not_hidden_as_a_blob(self):
        unknown=ResourceRecord.create(0x12345678,99,"Unknown",0,{0x12345678:b"opaque"})
        raw=ResourcePack.create("TEST.RPK",[unknown]).write()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source"
            with self.assertRaisesRegex(ValidationError,"inverse resource recipe"):
                export_pack_python(decode_pack(raw),source,mod_id=MOD_ID)
            self.assertFalse(source.exists())

    def test_extra_resource_fields_are_rejected(self):
        resource=ResourceRecord.create(0x471476,42,"Marker",0,{0x4714A3:FieldTable({9000:b"future"}).write()})
        raw=ResourcePack.create("TEST.RPK",[resource]).write()
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValidationError,"Unknown or missing"):
            export_pack_python(decode_pack(raw),Path(directory)/"source",mod_id=MOD_ID)

    def test_pack_store_and_record_metadata_are_checked(self):
        for kind in ("pack","record"):
            pack=ResourcePack.read(basic_project().build())
            if kind=="pack":pack.table.fields[9999]=b"future"
            else:
                store,group,index,record=next(pack.records())
                record.table.fields[23]=b"\x00";pack.replace_record(store,group,index,record)
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory,self.assertRaises(ValidationError):
                export_pack_python(decode_pack(pack.write()),Path(directory)/"source",mod_id=MOD_ID)

    def test_reference_is_optional_and_only_used_for_comparison(self):
        raw=basic_project().build()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/"source";reference=root/"original.rpk";reference.write_bytes(raw)
            export_pack_python(decode_pack(raw),source,mod_id=MOD_ID)
            report=build_pack_export(source,root/"rebuilt.rpk",reference=reference)
            self.assertTrue(report["equivalent"])
            self.assertEqual(reference.read_bytes(),raw)
            with self.assertRaisesRegex(ValidationError,"overwrite"):
                build_pack_export(source,reference,reference=reference)

    def test_edited_resource_value_is_detected_by_comparison(self):
        before=basic_project().build()
        after=replace(basic_project(),dependencies=("OTHER.RPK",)).build()
        self.assertFalse(compare_resource_packs(before,after)["equivalent"])

    def test_project_rejects_duplicate_ids_and_missing_identity(self):
        p=basic_project()
        for changed in [replace(p,definitions=(p.definitions[0],p.definitions[0])),
                        replace(p,definitions=(SideProperty(key="x",name="X"),)),
                        replace(p,mod_id=None)]:
            with self.assertRaises(ValidationError):changed.build()

    def test_cli_full_export_and_build(self):
        raw=basic_project().build()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);reference=root/"original.rpk";reference.write_bytes(raw)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["export-python",str(reference),"--scope","pack","--mod-id",str(MOD_ID),"--output",str(root/"source")]),0)
                self.assertEqual(main(["build-pack",str(root/"source"),"--output",str(root/"rebuilt.rpk"),"--reference",str(reference)]),0)
            self.assertFalse((root/"source/input.rpk").exists())

    def test_full_export_requires_uuid_and_protects_existing_source(self):
        decoded=decode_pack(basic_project().build())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"source"
            with self.assertRaises(ValidationError):export_pack_python(decoded,path,mod_id=None)
            export_pack_python(decoded,path,mod_id=MOD_ID)
            with self.assertRaises(ValidationError):export_pack_python(decoded,path,mod_id=MOD_ID)
