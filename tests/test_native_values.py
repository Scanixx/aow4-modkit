"""Synthetic native static-value tests; no game resources or mod assets."""
from dataclasses import replace
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

from aow4modkit import (ResourceHandle, ResourceLink, ResourceHandleList, EmptyTextContext,
    StrategicTargeterBinding, UnitRequisiteFilter, ArmyTargetConditions, AtlasSpriteReference,
    EnvironmentReference, AtlasRenderParameters, TextureAtlasRegion, SpellUnlockProperty,
    ResourcePackProject, PreservedParameter, ValidationError)
from aow4modkit.analysis import decode_pack, export_pack_python, compare_resource_packs
from aow4modkit.formats.binary import FieldTable, U32
from aow4modkit.native_values import ARMY_CONDITIONS_CLASS, ATLAS_REGION_CLASS


def sample_values():
    handles = ResourceHandleList((ResourceHandle(101,"Example A"),ResourceHandle(102,"Example B")))
    icon = TextureAtlasRegion(AtlasSpriteReference("[EXAMPLE]TXA\\0","Example icon"),
        ResourceLink(103,"Example profile","[#0000000000000067]0\\0"),
        EnvironmentReference("EXAMPLE.ENV","Example"))
    return (ResourceHandleList(), handles, replace(handles,compact=False), EmptyTextContext(),
        StrategicTargeterBinding(replace(handles,compact=False)),
        UnitRequisiteFilter(native_field_4=handles), ArmyTargetConditions(native_field_3=handles),
        icon.sprite, icon.environment, icon.render_parameters, icon)


class NativeValueTests(unittest.TestCase):
    def test_each_structure_roundtrips_every_byte(self):
        for value in sample_values():
            with self.subTest(kind=type(value).__name__):
                raw=value.encode();decoded=type(value).decode(raw)
                self.assertEqual(decoded.encode(),raw)

    def test_lists_preserve_order_and_both_directory_layouts(self):
        _,compact,wide,*_=sample_values()
        self.assertNotEqual(compact.encode(),wide.encode())
        self.assertEqual(ResourceHandleList.decode(wide.encode()).handles,compact.handles)
        reversed_list=replace(compact,handles=tuple(reversed(compact.handles)))
        self.assertNotEqual(reversed_list.encode(),compact.encode())

    def test_float32_parameters_are_reconstructed_from_numbers(self):
        value=AtlasRenderParameters((1.25,-2.5,7.0),0.8)
        decoded=AtlasRenderParameters.decode(value.encode())
        self.assertEqual(decoded.native_vector_0,value.native_vector_0)
        self.assertEqual(struct.pack('<f',decoded.native_scalar_3),struct.pack('<f',0.8))
        self.assertNotEqual(replace(value,native_scalar_3=0.5).encode(),value.encode())

    def test_unknown_fields_are_not_silently_dropped(self):
        for value in sample_values():
            table=FieldTable.read(value.encode());table.fields[9999]=b'future'
            with self.subTest(kind=type(value).__name__),self.assertRaises(ValidationError):
                type(value).decode(table.write())

    def test_unknown_nested_conditions_fields_fail(self):
        value=ArmyTargetConditions();outer=FieldTable.read(value.encode())
        inner=FieldTable.read(outer.fields[ARMY_CONDITIONS_CLASS]);inner.fields[99]=b'future'
        outer.fields[ARMY_CONDITIONS_CLASS]=inner.write()
        with self.assertRaises(ValidationError):ArmyTargetConditions.decode(outer.write())

    def test_invalid_values_and_flags_fail(self):
        for value in (ArmyTargetConditions(native_field_1=-1),
                      StrategicTargeterBinding(ResourceHandleList(),True),
                      AtlasRenderParameters((0,0,float('nan'))),
                      AtlasRenderParameters((0,0)),
                      replace(sample_values()[-1],native_flag_54=1)):
            with self.subTest(value=value),self.assertRaises(ValidationError):value.encode()
        value=sample_values()[-1];outer=FieldTable.read(value.encode())
        row=FieldTable.read(outer.fields[ATLAS_REGION_CLASS]);row.fields[54]=b'\2'
        outer.fields[ATLAS_REGION_CLASS]=row.write()
        with self.assertRaises(ValidationError):TextureAtlasRegion.decode(outer.write())

    def test_invalid_handle_class_and_indices_fail(self):
        value=ResourceHandleList((ResourceHandle(1,"Example"),))
        outer=FieldTable.read(value.encode());middle=FieldTable.read(outer.fields[30])
        rows=FieldTable.read(middle.fields[1]);rows.fields[0]=U32.pack(999)+rows.fields[0][4:]
        middle.fields[1]=rows.write();outer.fields[30]=middle.write()
        with self.assertRaises(ValidationError):ResourceHandleList.decode(outer.write())
        rows.fields={2:rows.fields[0]};middle.fields[1]=rows.write();outer.fields[30]=middle.write()
        with self.assertRaises(ValidationError):ResourceHandleList.decode(outer.write())

    def test_typed_export_has_no_static_hex_sidecar_and_rebuilds(self):
        definition=SpellUnlockProperty(key="unlock",name="Unlock",resource_id=42,parameters=dict(
            empty_title=EmptyTextContext(),empty_description=EmptyTextContext(),
            native_unlock_flag_3=False,operations=(ResourceHandle(99,"Example operation"),)))
        raw=ResourcePackProject("EXAMPLE.RPK","00000000-0000-0000-0000-000000000001",(definition,)).build()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source"
            manifest=export_pack_python(decode_pack(raw),source,mod_id="00000000-0000-0000-0000-000000000001")
            self.assertEqual(manifest['preserved_static_parameters'],0)
            self.assertFalse((source/'preserved-parameters.json').exists())
            text=next((source/'resources').glob('*.py')).read_text()
            self.assertIn('EmptyTextContext()',text)
            self.assertNotIn('fromhex',text)
            rebuilt=runpy.run_path(str(source/'resources.py'))['build_pack']().build()
            self.assertTrue(compare_resource_packs(raw,rebuilt)['equivalent'])

    def test_legacy_preserved_parameter_still_emits_identical_bytes(self):
        def build(value):
            definition=SpellUnlockProperty(key="unlock",name="Unlock",resource_id=42,parameters=dict(
                empty_title=value,empty_description=value,native_unlock_flag_3=False,operations=()))
            return ResourcePackProject("EXAMPLE.RPK","00000000-0000-0000-0000-000000000001",(definition,)).build()
        self.assertEqual(build(EmptyTextContext()),build(PreservedParameter(EmptyTextContext().encode(),"Legacy empty text")))

    def test_atlas_export_retains_every_named_value(self):
        from aow4modkit import TextureAtlasIcon
        icon=sample_values()[-1]
        def build(value):
            definition=TextureAtlasIcon(key="icon",name="Example icon",resource_id=42,
                parameters=dict(atlas_region=value))
            return ResourcePackProject("EXAMPLE.RPK","00000000-0000-0000-0000-000000000001",(definition,)).build()
        original=build(icon)
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"source"
            export_pack_python(decode_pack(original),source,mod_id="00000000-0000-0000-0000-000000000001")
            rebuilt=runpy.run_path(str(source/'resources.py'))['build_pack']().build()
            self.assertEqual(original,rebuilt)
            text=next((source/'resources').glob('*.py')).read_text()
            for name in ('TextureAtlasRegion','AtlasSpriteReference','EnvironmentReference','AtlasRenderParameters'):
                self.assertIn(name+'(',text)
        changes=(replace(icon,sprite=replace(icon.sprite,region_name="Other region")),
                 replace(icon,native_flag_54=True),
                 replace(icon,render_parameters=replace(icon.render_parameters,native_scalar_3=0.5)),
                 replace(icon,environment=replace(icon.environment,path="OTHER.ENV")))
        for changed in changes:
            with self.subTest(changed=changed):
                self.assertFalse(compare_resource_packs(original,build(changed))['equivalent'])

    def test_decoding_rejects_nonfinite_native_float(self):
        raw=AtlasRenderParameters().encode()
        raw=raw[:-4]+struct.pack('<f',float('nan'))
        with self.assertRaises(ValidationError):AtlasRenderParameters.decode(raw)

    def test_comparison_ignores_handle_framing_but_detects_reference_changes(self):
        from aow4modkit import ArmyTargeter
        compact=ResourceHandleList((ResourceHandle(101,"Example requisite"),))
        def build(handles):
            definition=ArmyTargeter(key="targeter",name="Example targeter",resource_id=42,
                parameters=dict(properties=(),native_targeter_value_9=0,target_mode=3,
                    unit_requisite_filter=UnitRequisiteFilter(native_field_4=handles),
                    native_army_flag_3=True,target_conditions=ArmyTargetConditions()))
            return ResourcePackProject("EXAMPLE.RPK","00000000-0000-0000-0000-000000000001",(definition,)).build()
        original=build(compact);wide=build(replace(compact,compact=False))
        self.assertNotEqual(original,wide)
        self.assertTrue(compare_resource_packs(original,wide)['equivalent'])
        changed=build(replace(compact,handles=(ResourceHandle(101,"Renamed requisite"),)))
        self.assertFalse(compare_resource_packs(original,changed)['equivalent'])
