"""Synthetic full-RPK inverse ascension tests; no game assets or real IDs."""
from dataclasses import replace
from pathlib import Path
import runpy
import tempfile
import unittest
from uuid import UUID

from aow4modkit import (ResourcePackProject,TagBook,TagDefinition,HiddenArtifactMarker,
    AscensionTrait,HeroSkill,SideProperty,LocalizedText,ResourceLink,Trigger,actions,events,ValidationError)
from aow4modkit.analysis import decode_pack,export_pack_python,compare_resource_packs
from aow4modkit.formats.binary import FieldTable, U32
from aow4modkit.formats.rpk import ResourcePack
from aow4modkit.constants import ClassId as C

MOD_ID=UUID(int=1)


def example_project():
    book=TagBook(key='tags',name='Example tags',resource_id=4,root='Example',root_guid=UUID(int=2),
        tags=(TagDefinition('First',UUID(int=3)),TagDefinition('Second',UUID(int=4))))
    title=LocalizedText('EXAMPLE@NAME');description=LocalizedText('EXAMPLE@DESCRIPTION')
    icon=ResourceLink(99,'Example icon','[#0000000000000063]0\\0')
    token=HiddenArtifactMarker(key='token',name='Example marker',resource_id=1,title=title,
        description=description,lore=description,forge_description=description,tags=(book.tag('First'),))
    trait=AscensionTrait(key='trait',name='Example trait',resource_id=2,title=title,description=description,
        icon=icon,requires_tag=book.tag('First'),skills=(ResourceLink(3,'Example skill','[#0000000000000003]0\\2'),))
    skill=HeroSkill(key='skill',name='Example skill',resource_id=3,title=title,description=description,
        icon=icon,ai_priority=icon,group=icon,side_properties=())
    trigger=Trigger('trigger',[events.new_turn()],[actions.log('Example')],resource_id=5,name='Example trigger')
    return ResourcePackProject('EXAMPLE.RPK',MOD_ID,(token,trait,skill,book,trigger))


def edit_record(raw,uid,edit):
    pack=ResourcePack.read(raw)
    for store,group,index,record in pack.records():
        if record.resource_id==uid:
            edit(record);pack.replace_record(store,group,index,record);return pack.write()
    raise AssertionError('Missing synthetic record')


class AscensionExportTests(unittest.TestCase):
    def test_all_recipes_export_through_public_constructors_without_blobs(self):
        raw=example_project().build()
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source'
            manifest=export_pack_python(decode_pack(raw),source,mod_id=MOD_ID)
            self.assertEqual(manifest['resource_count'],5)
            self.assertEqual(manifest['preserved_static_parameters'],0)
            self.assertFalse(list(source.rglob('*.rpk')))
            texts='\n'.join(p.read_text(encoding='utf-8') for p in (source/'resources').glob('*.py'))
            for name in ('TagBook','TagDefinition','TagRef','HiddenArtifactMarker','AscensionTrait','HeroSkill'):
                self.assertIn(name+'(',texts)
            self.assertNotIn('fromhex',texts)
            rebuilt=runpy.run_path(str(source/'resources.py'))['build_pack']().build()
            self.assertTrue(compare_resource_packs(raw,rebuilt)['equivalent'])

    def test_changed_profile_default_is_rejected_instead_of_lost(self):
        def edit(record):
            fields=record.class_fields(C.TOKEN);fields.fields[20]=b'\1';record.table.fields[C.TOKEN]=fields.write()
        raw=edit_record(example_project().build(),1,edit)
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'source'
            with self.assertRaisesRegex(ValidationError,'defaults/structure'):
                export_pack_python(decode_pack(raw),output,mod_id=MOD_ID)
            self.assertFalse(output.exists())

    def test_additional_grants_and_unknown_classes_are_not_dropped(self):
        for cls in (C.TOKEN,C.HERO_SKILL):
            uid=1 if cls==C.TOKEN else 3
            def edit(record):record.table.fields[0xABCDEF]=FieldTable({}).write()
            raw=edit_record(example_project().build(),uid,edit)
            with tempfile.TemporaryDirectory() as directory,self.assertRaises(ValidationError):
                export_pack_python(decode_pack(raw),Path(directory)/'source',mod_id=MOD_ID)

    def test_nonflat_tag_topology_is_rejected(self):
        def edit(record):
            raw=record.table.fields[0];nodes=FieldTable.read(raw,3);node=FieldTable.read(nodes.fields[2])
            identity=node.fields[0];node.fields[0]=identity[:16]+bytes(16)+identity[32:]
            nodes.fields[2]=node.write();record.table.fields[0]=raw[:3]+nodes.write()
        raw=edit_record(example_project().build(),4,edit)
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValidationError,'topology'):
            export_pack_python(decode_pack(raw),Path(directory)/'source',mod_id=MOD_ID)

    def test_missing_owned_book_is_not_replaced_by_a_fabricated_reference(self):
        def edit(record):
            record.class_id=C.SIDE_PROPERTY
            record.table.fields={k:v for k,v in record.table.fields.items() if k<0x10000 and k!=0}
            record.table.fields[C.SIDE_PROPERTY_BASE]=FieldTable({}).write()
        raw=edit_record(example_project().build(),4,edit)
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValidationError,'owned tag book'):
            export_pack_python(decode_pack(raw),Path(directory)/'source',mod_id=MOD_ID)

    def test_tag_guid_changes_are_detected_by_comparison(self):
        project=example_project();before=project.build();book=project.definitions[3]
        changed=replace(book,tags=(TagDefinition('First',UUID(int=10)),book.tags[1]))
        token=replace(project.definitions[0],tags=(changed.tag('First'),))
        trait=replace(project.definitions[1],requires_tag=changed.tag('First'))
        after=replace(project,definitions=(token,trait,project.definitions[2],changed,project.definitions[4])).build()
        self.assertFalse(compare_resource_packs(before,after)['equivalent'])

    def test_missing_recipe_fields_fail_with_validation_error(self):
        def edit(record):
            fields=record.class_fields(C.HERO_SKILL_BASE);del fields.fields[1]
            record.table.fields[C.HERO_SKILL_BASE]=fields.write()
        raw=edit_record(example_project().build(),3,edit)
        with tempfile.TemporaryDirectory() as directory,self.assertRaises(ValidationError):
            export_pack_python(decode_pack(raw),Path(directory)/'source',mod_id=MOD_ID)

    def test_corrupt_tag_count_is_bounded_before_allocating_indices(self):
        def edit(record):
            raw=record.table.fields[0];nodes=FieldTable.read(raw,3)
            nodes.fields[0]=U32.pack(0xFFFFFFFF);record.table.fields[0]=raw[:3]+nodes.write()
        raw=edit_record(example_project().build(),4,edit)
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValidationError,'inventory'):
            export_pack_python(decode_pack(raw),Path(directory)/'source',mod_id=MOD_ID)
