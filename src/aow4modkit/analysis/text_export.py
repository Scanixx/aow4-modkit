"""Strict text-context inverse adapter and public-API Python generation."""
import ast

from ..text_contexts import TextContext, text_description


def localized_description(raw):
    key,context=TextContext.decode(raw)
    return text_description(key,context)


def localized_expression(row):
    def call(name,*args,**kwargs):
        return ast.Call(ast.Name(name,ast.Load()),list(args),[ast.keyword(k,v) for k,v in kwargs.items()])
    entries=[call('TextSubstitution',token=ast.Constant(item['token']),value=ast.Constant(item['value']))
             for item in row['substitutions']]
    style=ast.Attribute(ast.Name('TextContextStyle',ast.Load()),row['style'].upper(),ast.Load())
    context=call('TextContext',style=style,substitutions=ast.Tuple(entries,ast.Load()),compact=ast.Constant(row['compact']))
    return call('LocalizedText',ast.Constant(row['key']),context=context)


def localized_module(rows):
    # Imported only when generating output, after python_export initializes.
    from .python_export import _statement
    module=ast.Module([
        ast.ImportFrom('aow4modkit',[ast.alias(name) for name in
            ('LocalizedText','TextContext','TextContextStyle','TextSubstitution')],0),
        ast.Assign([ast.Name('TEXTS',ast.Store())],ast.Dict(
            [ast.Constant(key) for key in rows],[localized_expression(row) for row in rows.values()]))],[])
    ast.fix_missing_locations(module)
    source='"""Catalog keys and native formatter metadata; translations live in MO files."""\n'
    source+='\n\n'.join(_statement(stmt) for stmt in module.body)+'\n'
    compile(source,'localized_texts.py','exec')
    return source.encode('utf-8')
