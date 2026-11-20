"""Strict inverse adapters for the existing public ascension recipes.

Only the flat tag-book topology and recipe defaults actually representable by
the API are accepted. Candidate recompilation checks every payload field;
unknown/default-changing data is never discarded or exported as a blob.
"""
from uuid import UUID

from ..constants import ClassId as C
from ..errors import ValidationError
from ..formats.binary import FieldTable, U32, U64, decode_string
from ..expressions import ResourceRef, ResourceLink
from ..resources import (TagBook, TagDefinition, TagRef, HiddenArtifactMarker,
    AscensionTrait, HeroSkill, LocalizedText, ResourceContext)
from ..text_contexts import TextContext

ASCENSION_CLASSES = {C.TAG_BOOK,C.TOKEN,C.ASCENSION_TRAIT,C.HERO_SKILL}


def _table(raw,keys=None):
    values=FieldTable.read(raw).fields
    if keys is not None and set(values)!=set(keys):
        raise ValidationError('Unsupported ascension field set')
    return values


def _uint(raw):
    if len(raw)!=4:raise ValidationError('Expected ascension uint32')
    return U32.unpack(raw)[0]


def _book_ref(raw):
    row=_table(raw,{1,2,4})
    if _uint(row[1])!=1 or len(row[2])!=8:
        raise ValidationError('Unsupported tag-book reference')
    return U64.unpack(row[2])[0],decode_string(row[4])


def _book_nodes(raw):
    if raw[:3]!=b'\1\0\0':raise ValidationError('Unsupported tag-book header')
    rows=_table(raw[3:]);count=_uint(rows.get(0,b''))
    if count<1 or count!=len(rows)-1 or set(rows)!=set(range(count+1)):
        raise ValidationError('Unsupported tag-book node inventory')
    result=[]
    for index in range(1,count+1):
        row=_table(rows[index],{0,1,2})
        if len(row[0])!=64:raise ValidationError('Unsupported tag-book node identity width')
        result.append((row[0],decode_string(row[1]),_book_ref(row[2])))
    return result


def tag_books(pack):
    """Decode flat owned books, preserving UUIDs, order and tree pointers."""
    result={}
    for _,_,_,record in pack.records():
        if record.class_id!=C.TAG_BOOK:continue
        if 0 not in record.table.fields:raise ValidationError('Missing tag-book nodes')
        nodes=_book_nodes(record.table.fields[0])
        definition=TagBook(key=f'resource_{record.resource_id:016x}',name=record.name,
            resource_id=record.resource_id,root=nodes[0][1],
            root_guid=UUID(bytes_le=nodes[0][0][:16]),
            tags=tuple(TagDefinition(name,UUID(bytes_le=identity[:16])) for identity,name,_ in nodes[1:]))
        expected=[definition.root_guid.bytes_le+bytes(32)+(definition.tags[0].guid.bytes_le if definition.tags else bytes(16))]
        for index,tag in enumerate(definition.tags):
            sibling=definition.tags[index+1].guid.bytes_le if index+1<len(definition.tags) else bytes(16)
            expected.append(tag.guid.bytes_le+definition.root_guid.bytes_le+sibling+bytes(16))
        if [row[0] for row in nodes]!=expected or any(row[2]!=(record.resource_id,record.name) for row in nodes):
            raise ValidationError('Tag-book topology or self-reference is not representable by TagBook')
        result[record.resource_id]=definition
    return result


def _tag(raw,books):
    row=_table(raw,{1,2,3})
    if len(row[1])!=16:raise ValidationError('Tag GUID must occupy sixteen bytes')
    uid,name=_book_ref(row[3]);book=books.get(uid)
    if book is None or book.name!=name:raise ValidationError('Tag requires a matching owned tag book')
    path=decode_string(row[2]);guid=UUID(bytes_le=row[1])
    matches=[tag for tag in book.tags if book.root+'.'+tag.name==path and tag.guid==guid]
    if len(matches)!=1:raise ValidationError('Tag path/GUID is not declared in its owned book')
    return book.tag(matches[0].name)


def _tags(raw,books):
    rows=_table(_table(raw,{1})[1]);count=_uint(rows.get(0,b''))
    if count!=len(rows)-1 or set(rows)!=set(range(count+1)):raise ValidationError('Unsupported tag-set indices')
    return tuple(_tag(rows[i],books) for i in range(1,count+1))


def _tag_meaning(raw):
    row=_table(raw,{1,2,3})
    return row[1].hex(),decode_string(row[2]),_book_ref(row[3])


def _filter_meaning(raw):
    rows=_table(_table(raw,{0})[0],{0,1,2})
    root=_table(rows[1],{0,1,3});empty=_table(root[0],{1,3})
    selected=_table(rows[2],{0,1,3})
    return (rows[0].hex(),{k:v.hex() for k,v in empty.items()},root[1].hex(),root[3].hex(),
        _tag_meaning(selected[0]),selected[1].hex(),selected[3].hex())


def _meaning(record):
    from .resource_export import _link,_handles,_localized
    payload={k:v for k,v in record.table.fields.items() if k>=0x10000 or record.class_id==C.TAG_BOOK and k==0}
    result={}
    for cls,raw in payload.items():
        if record.class_id==C.TAG_BOOK:
            result[cls]=[(identity.hex(),name,ref) for identity,name,ref in _book_nodes(raw)];continue
        values=_table(raw);converted={}
        for key,value in values.items():
            codec=None
            if cls==C.TOKEN:
                codec=_localized if key in (1,2,16,17) else _handles if key==12 else None
                if key==19:
                    rows=_table(_table(value,{1})[1]);count=_uint(rows.get(0,b''))
                    if count!=len(rows)-1 or set(rows)!=set(range(count+1)):raise ValidationError('Unsupported tag set')
                    converted[key]=[_tag_meaning(rows[i]) for i in range(1,count+1)];continue
            elif cls==C.ASCENSION_TRAIT:
                codec=_localized if key in (0,1) else _link if key==2 else _handles if key in (3,5) else _filter_meaning if key==4 else None
            elif cls==C.HERO_SKILL_BASE:
                codec=_localized if key in (1,2) else _link if key in (3,6) else _handles if key==17 else None
            elif cls==C.HERO_SKILL:codec=_link if key==6 else None
            converted[key]=codec(value) if codec else value.hex()
        result[cls]=converted
    return result


def decode_ascension(record,pack,profile,books):
    from .resource_export import _link,_handles
    from ..expressions import ResourceHandle
    def text(raw):
        key,context=TextContext.decode(raw);return LocalizedText(key,context)
    def link(raw):
        row=_link(raw);return ResourceLink(int(row['resource_id'],16),row['name'],row['url'])
    def handles(raw):
        return tuple(ResourceHandle(int(row['resource_id'],16),row['name']) for row in _handles(raw))
    identity=dict(key=f'resource_{record.resource_id:016x}',name=record.name,resource_id=record.resource_id)
    if record.class_id==C.TAG_BOOK:
        definition=books[record.resource_id]
        arguments=dict(root=definition.root,root_guid=definition.root_guid,tags=definition.tags)
    elif record.class_id==C.TOKEN:
        row=record.class_fields(C.TOKEN).fields
        arguments=dict(title=text(row[1]),description=text(row[2]),lore=text(row[16]),
            forge_description=text(row[17]),tags=_tags(row[19],books))
        definition=HiddenArtifactMarker(**identity,**arguments)
    elif record.class_id==C.ASCENSION_TRAIT:
        row=record.class_fields(C.ASCENSION_TRAIT).fields
        selected=_table(_table(_table(row[4],{0})[0],{0,1,2})[2],{0,1,3})
        arguments=dict(title=text(row[0]),description=text(row[1]),icon=link(row[2]),
            requires_tag=_tag(selected[0],books),skills=handles(row[5]))
        definition=AscensionTrait(**identity,**arguments)
    elif record.class_id==C.HERO_SKILL:
        base=record.class_fields(C.HERO_SKILL_BASE).fields;normal=record.class_fields(C.HERO_SKILL).fields
        arguments=dict(title=text(base[1]),description=text(base[2]),icon=link(base[3]),
            ai_priority=link(base[6]),group=link(normal[6]),side_properties=handles(base[17]))
        definition=HeroSkill(**identity,**arguments)
    else:raise ValidationError('No ascension inverse recipe')
    bindings={f'resource_{r.resource_id:016x}':ResourceRef(r.resource_id,r.name,
        f'[#{r.resource_id:016X}]0\\{index}',decode_string(pack.table.fields[22]),
        kind='tag_book' if r.class_id==C.TAG_BOOK else 'other') for _,_,index,r in pack.records()}
    context=ResourceContext(bindings,profile,{b.key:b for b in books.values()},serialized_links=True)
    candidate=definition.compile(context)
    if _meaning(record)!=_meaning(candidate):
        raise ValidationError(f'Ascension resource {record.resource_id:016X} differs from representable recipe defaults/structure')
    from ..text_contexts import text_description
    def describe(value):
        if isinstance(value,LocalizedText):return dict(text=text_description(value.key,value.context))
        if isinstance(value,ResourceLink):return dict(link=dict(resource_id=f'{value.resource_id:016X}',name=value.name,url=value.url))
        if isinstance(value,ResourceHandle):return dict(handles=[dict(resource_id=f'{value.resource_id:016X}',name=value.name)])
        if isinstance(value,UUID):return dict(uuid=str(value))
        if isinstance(value,TagRef):return dict(tag_ref=dict(book=value.book.key,path=value.path,guid=str(value.guid)))
        if isinstance(value,TagDefinition):return dict(tag_definition=dict(name=value.name,guid=str(value.guid)))
        if isinstance(value,tuple):
            if all(isinstance(v,ResourceHandle) for v in value):
                return dict(handles=[dict(resource_id=f'{v.resource_id:016X}',name=v.name) for v in value])
            return [describe(v) for v in value]
        return value
    return dict(constructor=type(definition).__name__,arguments={k:describe(v) for k,v in arguments.items()})
