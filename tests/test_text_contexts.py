"""Synthetic localized-text metadata tests, without commercial game data."""
from dataclasses import replace
from pathlib import Path
import runpy
import tempfile
import unittest

from aow4modkit import (LocalizedText, TextContext, TextContextStyle, TextSubstitution,
    ResourcePackProject, TextureAtlasIcon, ValidationError)
from aow4modkit.formats.binary import FieldTable, U32
from aow4modkit.resources import ResourceContext
from aow4modkit.profiles import DEFAULT_PROFILE
from aow4modkit.text_contexts import TEXT_FORMAT_CONTEXT_CLASS, TEXT_SUBSTITUTION_CLASS
from aow4modkit.analysis.text_export import localized_description, localized_module


class TextContextTests(unittest.TestCase):
    def test_all_layouts_roundtrip_exact_bytes(self):
        parameters=(TextSubstitution('{GLOBAL.Example.Hyperlink}'),TextSubstitution('{amount}','2 [example/]'))
        for style in TextContextStyle:
            for compact in (False,True):
                entries=() if style==TextContextStyle.KEY_ONLY else parameters
                context=TextContext(style,entries,compact)
                raw=context.encode('EXAMPLE@NAME');key,decoded=TextContext.decode(raw)
                self.assertEqual(key,'EXAMPLE@NAME')
                self.assertEqual(decoded,context)
                self.assertEqual(decoded.encode(key),raw)

    def test_empty_and_absent_parameter_values_are_distinct(self):
        absent=TextSubstitution('{example}');empty=replace(absent,value='')
        self.assertNotEqual(absent.encode(),empty.encode())
        self.assertEqual(TextSubstitution.decode(empty.encode()).value,'')
        self.assertIsNone(TextSubstitution.decode(absent.encode()).value)

    def test_mixed_narrow_wide_parameter_directory_roundtrips(self):
        entries=tuple(TextSubstitution('{parameter_'+str(i)+'}',str(i)*70) for i in range(6))
        context=TextContext(substitutions=entries)
        raw=context.encode('EXAMPLE@NAME');key,decoded=TextContext.decode(raw)
        self.assertEqual(decoded,context);self.assertEqual(decoded.encode(key),raw)
        formatter=FieldTable.read(FieldTable.read(raw).fields[2]).fields[TEXT_FORMAT_CONTEXT_CLASS]
        rows=FieldTable.read(FieldTable.read(formatter).fields[0]).fields[1]
        table=FieldTable.read(rows)
        self.assertGreater(table.narrow_count,0)
        self.assertLess(table.narrow_count,len(table.fields))

    def test_unicode_and_long_values_use_utf8_lengths(self):
        context=TextContext(substitutions=(TextSubstitution('{example}','Příliš žluťoučký 🐉'*40),))
        key='EXAMPLE@ŽLUŤOUČKÝ';decoded_key,decoded=TextContext.decode(context.encode(key))
        self.assertEqual(decoded_key,key);self.assertEqual(decoded,context)

    def test_unknown_root_and_nested_fields_fail(self):
        for context in (TextContext(),TextContext(TextContextStyle.DIALOG),TextContext.notification()):
            root=FieldTable.read(context.encode('EXAMPLE@NAME'));root.fields[99]=b'future'
            with self.assertRaises(ValidationError):TextContext.decode(root.write())
        root=FieldTable.read(TextContext().encode('EXAMPLE@NAME'))
        metadata=FieldTable.read(root.fields[2]);metadata.fields[123]=b'future';root.fields[2]=metadata.write()
        with self.assertRaises(ValidationError):TextContext.decode(root.write())

    def test_unknown_substitution_class_and_fields_fail(self):
        raw=TextSubstitution('{example}','x').encode()
        with self.assertRaises(ValidationError):TextSubstitution.decode(U32.pack(123)+raw[4:])
        outer=FieldTable.read(raw[4:]);inner=FieldTable.read(outer.fields[TEXT_SUBSTITUTION_CLASS])
        inner.fields[4]=b'future';outer.fields[TEXT_SUBSTITUTION_CLASS]=inner.write()
        with self.assertRaises(ValidationError):TextSubstitution.decode(raw[:4]+outer.write())

    def test_dialog_auxiliary_data_is_checked(self):
        root=FieldTable.read(TextContext(TextContextStyle.DIALOG).encode('EXAMPLE@NAME'))
        root.fields[1]=FieldTable({1:FieldTable({0:b'future'}).write()}).write()
        with self.assertRaises(ValidationError):TextContext.decode(root.write())

    def test_nonconsecutive_substitution_indices_fail(self):
        root=FieldTable.read(TextContext(substitutions=(TextSubstitution('{example}'),)).encode('EXAMPLE@NAME'))
        metadata=FieldTable.read(root.fields[2]);holder=FieldTable.read(metadata.fields[TEXT_FORMAT_CONTEXT_CLASS])
        group=FieldTable.read(holder.fields[0]);rows=FieldTable.read(group.fields[1])
        rows.fields={2:rows.fields[0]};group.fields[1]=rows.write();holder.fields[0]=group.write()
        metadata.fields[TEXT_FORMAT_CONTEXT_CLASS]=holder.write();root.fields[2]=metadata.write()
        with self.assertRaises(ValidationError):TextContext.decode(root.write())

    def test_invalid_authoring_values_fail(self):
        for action in (lambda:TextContext(style='dialog'),lambda:TextContext(compact=1),
                       lambda:TextContext(substitutions=[]),lambda:TextContext.notification().encode(''),
                       lambda:TextContext(TextContextStyle.KEY_ONLY,(TextSubstitution('{example}'),)),
                       lambda:TextSubstitution('',None),lambda:TextSubstitution('{example}',2)):
            with self.assertRaises(ValidationError):action()

    def test_key_can_change_without_reusing_original_serialized_key(self):
        context=TextContext(substitutions=(TextSubstitution('{example}','recorded'),))
        compiler=ResourceContext({},DEFAULT_PROFILE)
        raw=compiler.localized(LocalizedText('OTHER@NAME',context))
        key,decoded=TextContext.decode(raw)
        self.assertEqual(key,'OTHER@NAME');self.assertEqual(decoded,context)

    def test_legacy_byte_context_is_still_identical(self):
        compiler=ResourceContext({},DEFAULT_PROFILE)
        for context in (TextContext(),TextContext(TextContextStyle.DIALOG),TextContext.notification()):
            raw=context.encode('EXAMPLE@NAME')
            self.assertEqual(compiler.localized(LocalizedText('EXAMPLE@NAME',raw)),
                             compiler.localized(LocalizedText('EXAMPLE@NAME',context)))

    def test_python_output_uses_public_api_and_safe_string_literals(self):
        token="{example}'; __import__('missing'); #"
        context=TextContext(substitutions=(TextSubstitution(token,'recorded'),))
        description=localized_description(context.encode('EXAMPLE@NAME'))
        source=localized_module({'example':description}).decode('utf-8')
        self.assertNotIn('fromhex',source);self.assertNotIn('context_hex',source)
        self.assertIn('TextSubstitution(',source)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'texts.py';path.write_text(source,encoding='utf-8')
            texts=runpy.run_path(str(path))['TEXTS']
        self.assertEqual(texts['example'],LocalizedText('EXAMPLE@NAME',context))

    def test_parameter_value_changes_are_visible_in_inverse_data(self):
        original=TextContext(substitutions=(TextSubstitution('{amount}','1'),))
        changed=replace(original,substitutions=(TextSubstitution('{amount}','2'),))
        self.assertNotEqual(localized_description(original.encode('EXAMPLE@NAME')),
                            localized_description(changed.encode('EXAMPLE@NAME')))

    def test_unknown_formatter_blocks_export_without_writing_source(self):
        from aow4modkit import Trigger, events, players, localized_link, invoke
        from aow4modkit.analysis import decode_pack, export_trigger_python
        from aow4modkit.formats.binary import encode_string
        bad=FieldTable({1:encode_string('EXAMPLE@NAME'),2:b'unsupported formatter'}).write()
        # Legacy authoring still accepts explicit bytes; new inverse export
        # cannot claim to have decoded arbitrary formatter data.
        expr=localized_link(LocalizedText('EXAMPLE@NAME',bad))
        from aow4modkit import ResourceLink
        icon=ResourceLink(99,'Example icon','[#0000000000000063]0\\0')
        action=invoke('players.show_todo_event_at_position',player=players.triggering(),
            title=expr,body=expr,icon=icon,hover_icon=icon,
            position=invoke('positions.special_operation',special_operation=invoke('spells.triggering')),
            variables=invoke('pools.local'))
        trigger=Trigger('notice',[events.new_turn()],[action],resource_id=42,name='Example notice')
        raw=ResourcePackProject('EXAMPLE.RPK','00000000-0000-0000-0000-000000000001',(trigger,)).build()
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'source'
            from aow4modkit import ModKitError
            with self.assertRaises(ModKitError):
                export_trigger_python(decode_pack(raw),output,mod_id='00000000-0000-0000-0000-000000000001')
            self.assertFalse(output.exists())
