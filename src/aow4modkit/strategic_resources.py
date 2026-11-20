"""Public named recipes for the observed strategic spell/dialog subset.

Static formatter/render/target parameters use typed native structures. Legacy
authored recipes can still preserve their previously audited bytes explicitly.
Executable trigger graphs always use typed Script/Expr definitions, never an
opaque old RPK or serialized script blob.
"""
from dataclasses import dataclass, field
from importlib.resources import files
import json

from .compiler import Script
from .constants import ClassId
from .errors import ValidationError
from .formats.binary import FieldTable, U32
from .formats.rpk import ResourceRecord
from .resources import ResourceDefinition, LocalizedText
from .native_values import NativeValue, NATIVE_TYPES


@dataclass(frozen=True)
class PreservedParameter:
    """An explicitly retained static wire value whose full schema is unknown.

    Supply a human description. Do not use this to hide executable scripts or
    complete resources. Independent migration audits must compare these bytes.
    """
    data: bytes
    description: str

    def __post_init__(self):
        if not isinstance(self.data, bytes) or not self.description:
            raise ValidationError("PreservedParameter needs bytes and a meaningful description")


@dataclass(frozen=True)
class DialogChoice:
    list_id: int
    text: LocalizedText
    category: object
    action: Script
    visibility: Script
    visibility_mode: int = 4


@dataclass(frozen=True, kw_only=True)
class ProfileResource(ResourceDefinition):
    """A supported named recipe selected from the versioned strategic schema."""
    schema: str
    parameters: dict

    def compile(self, context):
        data = json.loads(files("aow4modkit").joinpath(
            "resource_schemas", "strategic_2_3.json").read_text(encoding="utf-8"))
        if data["profile"] != context.profile.key or self.schema not in data["resources"]:
            raise ValidationError(f"Unsupported resource recipe/profile: {self.schema}")
        spec = data["resources"][self.schema]
        required = {item["name"] for cls in spec["classes"] for item in cls["fields"]}
        if set(self.parameters) != required:
            raise ValidationError(f"{self.key} parameters differ from schema; missing={sorted(required-set(self.parameters))}, extra={sorted(set(self.parameters)-required)}")
        classes = {}
        for cls in spec["classes"]:
            values = {}
            for item in cls["fields"]:
                value = self.parameters[item["name"]]
                codec = item["codec"]
                if codec == "link":
                    encoded = context.link(value)
                elif codec == "links":
                    encoded = context.light_links(value)
                elif codec == "localized":
                    encoded = context.localized(value)
                elif codec == "u32":
                    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
                        raise ValidationError("u32 recipe parameter outside its range")
                    encoded = U32.pack(value)
                elif codec == "bool":
                    if type(value) is not bool:
                        raise ValidationError("Boolean recipe parameter must be bool")
                    encoded = bytes([value])
                elif codec == "preserved":
                    if isinstance(value, PreservedParameter):
                        encoded = value.data  # Backward-compatible authored recipes.
                    elif isinstance(value, NativeValue) and type(value) is NATIVE_TYPES.get(item.get("native_type")):
                        encoded = value.encode(context)
                    else:
                        raise ValidationError(f"Static field requires {item.get('native_type', 'PreservedParameter')}")
                elif codec == "script":
                    encoded = context.script(self, value)
                elif codec == "choices":
                    encoded = self._choices(context, value)
                else:
                    raise ValidationError(f"No verified field codec named {codec}")
                values[item["field"]] = encoded
            classes[int(cls["class_id"], 16)] = FieldTable(values).write()
        return context.record(self, int(spec["class_id"], 16), classes)

    def _choices(self, context, choices):
        if any(not isinstance(choice, DialogChoice) for choice in choices):
            raise ValidationError("Expected DialogChoice definitions")
        identifiers = [choice.list_id for choice in choices]
        if len(set(identifiers)) != len(identifiers) or any(type(i) is not int or not 0 <= i < 255 for i in identifiers):
            raise ValidationError("Dialog choices need unique list IDs in 0..254")
        rows = {}
        for index, choice in enumerate(choices):
            if type(choice.visibility_mode) is not int or not 0 <= choice.visibility_mode <= 0xFFFFFFFF:
                raise ValidationError("Dialog visibility mode must fit u32")
            fields = {0: bytes([choice.list_id]), 2: context.script(self, choice.action),
                      3: context.link(choice.category), 4: U32.pack(choice.visibility_mode),
                      5: context.localized(choice.text), 6: context.script(self, choice.visibility)}
            rows[index] = ResourceRecord(ClassId.STORY_EVENT_CHOICE, FieldTable(fields)).write()
        entries = FieldTable({1: FieldTable(rows).write()}).write()
        return FieldTable({0: bytes([max(identifiers, default=-1)+1]), 1: entries}).write()


@dataclass(frozen=True, kw_only=True)
class StrategicArmySpell(ProfileResource):
    schema: str = field(default="strategic_army_spell", init=False)
    kind = "spell_resource"


@dataclass(frozen=True, kw_only=True)
class ArmyTargeter(ProfileResource):
    schema: str = field(default="army_targeter", init=False)
    kind = "targeter"


@dataclass(frozen=True, kw_only=True)
class ResearchSkill(ProfileResource):
    schema: str = field(default="research_skill", init=False)
    kind = "research_skill"


@dataclass(frozen=True, kw_only=True)
class SpellUnlockProperty(ProfileResource):
    schema: str = field(default="spell_unlock_property", init=False)
    kind = "side_property"


@dataclass(frozen=True, kw_only=True)
class TextureAtlasIcon(ProfileResource):
    schema: str = field(default="texture_atlas_icon", init=False)
    kind = "icon"


@dataclass(frozen=True, kw_only=True)
class StoryEvent(ProfileResource):
    schema: str = field(default="story_event", init=False)
    kind = "story_event_resource"
