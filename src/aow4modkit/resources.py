"""Named authoring recipes for the observed 2.3 ascension-resource subset.

Binary field IDs and opaque structural defaults stay in this layer, not in mod
source. Recipes do not clone native resources or require installed game files.
"""
from dataclasses import dataclass, fields, is_dataclass
from importlib.resources import files
import json
import struct
from uuid import UUID

from .constants import (ClassId, TokenField, AscensionField, HeroSkillField,
                        HeroSkillNormalField)
from .errors import ValidationError
from .expressions import ResourceRef, OwnedResourceRef
from .formats.binary import FieldTable, U32, U64, encode_string
from .formats.rpk import ResourceRecord

Reference = ResourceRef | OwnedResourceRef


def _table(fields, narrow=0):
    return FieldTable(fields, narrow).write()


def iter_references(value):
    """Find declared links without guessing resource IDs inside opaque bytes."""
    if isinstance(value, (ResourceRef, OwnedResourceRef)):
        yield value
    elif is_dataclass(value):
        for field in fields(value):
            yield from iter_references(getattr(value, field.name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from iter_references(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_references(item)


@dataclass(frozen=True)
class LocalizedText:
    """A catalog key plus optional preserved localized-link parameter context.

    ``context`` is structural migration metadata, not the translated string.
    Ordinary authors should use just the key. It is retained byte-for-byte
    apart from replacing its key, avoiding changes to old formatter parameters.
    """
    key: str
    context: bytes | None = None


@dataclass(frozen=True)
class TagDefinition:
    name: str
    guid: UUID


@dataclass(frozen=True)
class TagRef:
    book: OwnedResourceRef
    path: str
    guid: UUID


class ResourceContext:
    """Public recipe compilation context supplied by ModProject."""
    def __init__(self, bindings, profile, definitions=None, mod_id=None):
        self.bindings, self.profile = bindings, profile
        self.definitions = definitions or {}
        self.mod_id = mod_id
        self._script_compilers = {}
        if profile.key != "aow4-2.3-observed-v1":
            raise ValidationError(f"Ascension recipes have no verified schema for profile {profile.key}")
        self.defaults = json.loads(files("aow4modkit").joinpath(
            "resource_schemas", "ascension_2_3.json").read_text(encoding="utf-8"))

    def resolve(self, ref: Reference) -> ResourceRef:
        if isinstance(ref, OwnedResourceRef):
            if ref.key not in self.bindings:
                raise ValidationError(f"Unresolved owned reference: {ref.key}")
            actual = self.bindings[ref.key]
            if ref.kind != "other" and actual.kind != ref.kind:
                raise ValidationError(f"Owned reference {ref.key} expects {ref.kind}, got {actual.kind}")
            return actual
        if isinstance(ref, ResourceRef):
            return ref
        raise ValidationError("Expected a resource reference")

    def link(self, ref: Reference, expected_kind=None) -> bytes:
        value = self.resolve(ref)
        if expected_kind and value.kind not in ("other", expected_kind):
            raise ValidationError(f"Expected {expected_kind} link, got {value.kind}")
        return _table({20: encode_string(value.url), 22: U64.pack(value.resource_id), 23: encode_string(value.name)})

    def light_links(self, refs, expected_kind=None) -> bytes:
        values = [self.resolve(ref) for ref in refs]
        if expected_kind and any(value.kind not in ("other", expected_kind) for value in values):
            raise ValidationError(f"Expected only {expected_kind} light links")
        return _table({30: _table({1: _table({i: U32.pack(0x40004A) + _table(
            {20: U64.pack(value.resource_id), 22: encode_string(value.name)})
            for i, value in enumerate(values)})})})

    def localized(self, text: LocalizedText) -> bytes:
        if not isinstance(text, LocalizedText) or not text.key:
            raise ValidationError("Localized resource fields need a nonempty LocalizedText key")
        if text.context is not None:
            table = FieldTable.read(text.context)
            inner = FieldTable.read(table.fields[0]) if 0 in table.fields else table
            if 1 not in inner.fields:
                raise ValidationError("Localized context must contain its key field")
            inner.fields[1] = encode_string(text.key)
            if 0 in table.fields:
                table.fields[0] = inner.write()
            return table.write()
        return _table({1: encode_string(text.key),
                       2: bytes.fromhex(self.defaults["localized_metadata"])}, narrow=2)

    def book_reference(self, ref: OwnedResourceRef) -> bytes:
        value = self.resolve(ref)
        if value.kind != "tag_book":
            raise ValidationError("Tag references must point to an owned tag book")
        return _table({1: U32.pack(1), 2: U64.pack(value.resource_id), 4: encode_string(value.name)}, narrow=3)

    def tag(self, tag: TagRef) -> bytes:
        book = self.definitions.get(tag.book.key)
        if book is not None:
            if not isinstance(book, TagBook) or not any(
                    book.root + "." + item.name == tag.path and item.guid == tag.guid for item in book.tags):
                raise ValidationError(f"Tag is not declared in book {tag.book.key}: {tag.path}")
        return _table({1: tag.guid.bytes_le, 2: encode_string(tag.path),
                       3: self.book_reference(tag.book)}, narrow=3)

    def tag_set(self, tags) -> bytes:
        return _table({1: _table({0: U32.pack(len(tags)), **{
            i: self.tag(tag) for i, tag in enumerate(tags, 1)}}, narrow=len(tags)+1)}, narrow=1)

    def tag_filter(self, tag: TagRef) -> bytes:
        # Observed native single-tag filter: retain the empty/root selector and
        # tag-selector metadata instead of inventing a different filter kind.
        empty = _table({1: bytes(16), 3: b"\x00"}, narrow=2)
        root_selector = _table({0: empty, 1: U32.pack(2),
                                3: bytes.fromhex("00000000ffffffffffffffff01000000")}, narrow=3)
        tag_selector = _table({0: self.tag(tag), 1: U32.pack(10),
                               3: bytes.fromhex("0100000000000000ffffffffffffffff")}, narrow=3)
        return _table({0: _table({0: U32.pack(2), 1: root_selector, 2: tag_selector}, narrow=3)}, narrow=1)

    def record(self, definition, class_id, classes) -> ResourceRecord:
        ref = self.bindings[definition.key]
        index = int(ref.url.rsplit("\\", 1)[1])
        return ResourceRecord.create(class_id, ref.resource_id, ref.name, index, classes)

    def script(self, definition, script):
        from .compiler import Script, TriggerCompiler
        if not isinstance(script, Script):
            raise ValidationError("Embedded script fields need a public Script definition")
        if self.mod_id is None:
            raise ValidationError("Script compilation requires a project UUID")
        if definition.key not in self._script_compilers:
            self._script_compilers[definition.key] = TriggerCompiler(
                self.mod_id, self.bindings[definition.key].resource_id, self.profile, self.bindings)
        return self._script_compilers[definition.key].compile_script(script)


@dataclass(frozen=True, kw_only=True)
class ResourceDefinition:
    key: str
    name: str | None = None
    resource_id: int | None = None
    kind = "other"

    def references(self):
        return iter_references(self)

    def compile(self, context: ResourceContext):
        raise ValidationError(f"No serializer for resource recipe {type(self).__name__}")


@dataclass(frozen=True, kw_only=True)
class TagBook(ResourceDefinition):
    root: str
    root_guid: UUID
    tags: tuple[TagDefinition, ...]
    kind = "tag_book"

    def tag(self, name: str) -> TagRef:
        matches = [tag for tag in self.tags if tag.name == name]
        if len(matches) != 1:
            raise ValidationError(f"Tag book has no unique tag named {name}")
        return TagRef(OwnedResourceRef(self.key, self.kind), self.root + "." + name, matches[0].guid)

    def compile(self, context: ResourceContext):
        names = [tag.name for tag in self.tags]
        guids = [tag.guid for tag in self.tags]
        if not self.root or not isinstance(self.root_guid, UUID) or any(
                not tag.name or not isinstance(tag.guid, UUID) for tag in self.tags):
            raise ValidationError("Tag books need a root name, nonempty tag names and UUID identities")
        if len(set(names)) != len(names) or len(set(guids + [self.root_guid])) != len(guids)+1:
            raise ValidationError("Tag names and GUIDs must be unique in a book")
        book = OwnedResourceRef(self.key, self.kind)
        reference = context.book_reference(book)
        first = self.tags[0].guid.bytes_le if self.tags else bytes(16)
        root = _table({0: self.root_guid.bytes_le + bytes(32) + first,
                       1: encode_string(self.root), 2: reference}, narrow=3)
        nodes = {0: U32.pack(len(self.tags)+1), 1: root}
        for index, tag in enumerate(self.tags, 2):
            sibling = self.tags[index-1].guid.bytes_le if index-1 < len(self.tags) else bytes(16)
            nodes[index] = _table({0: tag.guid.bytes_le + self.root_guid.bytes_le + sibling + bytes(16),
                                   1: encode_string(tag.name), 2: reference}, narrow=3)
        return context.record(self, ClassId.TAG_BOOK, {0: b"\x01\x00\x00" + _table(nodes)})


@dataclass(frozen=True, kw_only=True)
class HiddenArtifactMarker(ResourceDefinition):
    title: LocalizedText
    description: LocalizedText
    lore: LocalizedText
    forge_description: LocalizedText
    tags: tuple[TagRef, ...]
    kind = "token"

    def compile(self, context: ResourceContext):
        f = TokenField
        values = {f.NAME: context.localized(self.title), f.DESCRIPTION: context.localized(self.description),
                  f.VALUE: struct.pack("<f", 0.0), f.TEXT_ICON: b"\x00", f.PROPERTIES: context.light_links(()),
                  f.ICON: b"\x00", f.LORE: context.localized(self.lore),
                  f.FORGE_DESCRIPTION: context.localized(self.forge_description), f.TYPE: U32.pack(1),
                  f.TAGS: context.tag_set(self.tags), f.ALWAYS_VISIBLE: b"\x00", f.SHOW_OPERATION: b"\x00"}
        return context.record(self, ClassId.TOKEN, {ClassId.TOKEN: _table(values)})


@dataclass(frozen=True, kw_only=True)
class AscensionTrait(ResourceDefinition):
    title: LocalizedText
    description: LocalizedText
    icon: Reference
    requires_tag: TagRef
    skills: tuple[Reference, ...]
    kind = "ascension_trait"

    def compile(self, context: ResourceContext):
        f = AscensionField
        values = {f.NAME: context.localized(self.title), f.DESCRIPTION: context.localized(self.description),
                  f.ICON: context.link(self.icon, "icon"), f.UNIT_PROPERTIES: context.light_links(()),
                  f.AVAILABILITY: context.tag_filter(self.requires_tag), f.HERO_SKILLS: context.light_links(self.skills, "hero_skill")}
        return context.record(self, ClassId.ASCENSION_TRAIT, {ClassId.ASCENSION_TRAIT: _table(values)})


@dataclass(frozen=True, kw_only=True)
class HeroSkill(ResourceDefinition):
    title: LocalizedText
    description: LocalizedText
    icon: Reference
    ai_priority: Reference
    group: Reference
    side_properties: tuple[Reference, ...]
    kind = "hero_skill"

    def compile(self, context: ResourceContext):
        base = {int(k): bytes.fromhex(v) for k, v in context.defaults["hero_skill_base_defaults"].items()}
        normal = {int(k): bytes.fromhex(v) for k, v in context.defaults["hero_skill_normal_defaults"].items()}
        f = HeroSkillField
        base.update({f.NAME: context.localized(self.title), f.DESCRIPTION: context.localized(self.description),
                     f.ICON: context.link(self.icon, "icon"), f.AI_PRIORITY: context.link(self.ai_priority, "ai_priority"),
                     f.SIDE_PROPERTIES: context.light_links(self.side_properties, "side_property")})
        normal[HeroSkillNormalField.GROUP] = context.link(self.group, "hero_skill_group")
        return context.record(self, ClassId.HERO_SKILL, {ClassId.HERO_SKILL_BASE: _table(base), ClassId.HERO_SKILL: _table(normal)})


@dataclass(frozen=True, kw_only=True)
class SideProperty(ResourceDefinition):
    """A generic inert side-property marker, with no grants or hidden income."""
    kind = "side_property"

    def compile(self, context: ResourceContext):
        return context.record(self, ClassId.SIDE_PROPERTY, {ClassId.SIDE_PROPERTY_BASE: _table({})})
