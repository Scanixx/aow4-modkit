"""Named IDs for the supported format subset, not a complete engine SDK.

IDs identify serialized classes/fields/functions; they are NOT memory addresses.
Opaque profile fields deliberately retain neutral names instead of invented
semantics. See docs/compatibility.md for evidence and verification boundaries.
"""
from enum import IntEnum


class ClassId(IntEnum):
    RESOURCE_TAGS = 0x402000
    TRIGGER_CALL = 0x474244
    COMPARISON_PRESET = 0x474245
    TRIGGER_LIST = 0x474246
    TRIGGER = 0x474247
    INTEGER_PRESET = 0x47424D
    RESOURCE_LINK_PRESET = 0x474252
    BOOLEAN_PRESET = 0x474263
    STRING_PRESET = 0x474265
    VARIABLE_NAME_PRESET = 0x4743A8
    LOCALIZED_LINK_PRESET = 0x4778C0
    TRIGGER_SETTINGS = 0x47432E
    TOKEN = 0x470239
    ASCENSION_TRAIT = 0x475105
    HERO_SKILL = 0x471D55
    HERO_SKILL_BASE = 0x476E50
    SIDE_PROPERTY = 0x471476
    SIDE_PROPERTY_BASE = 0x4714A3
    TAG_BOOK = 0x40141D
    STORY_EVENT = 0x474393
    STORY_EVENT_BASE = 0x4774F0
    STORY_EVENT_CHOICE = 0x474397


class StoryEventBaseField(IntEnum):
    INITIALIZATION = 1


class StoryEventField(IntEnum):
    CHOICES = 4


class StoryChoiceField(IntEnum):
    LIST_ID = 0
    ACTION = 2
    CATEGORY = 3
    VISIBILITY_MODE = 4
    TEXT = 5
    VISIBILITY = 6


class ResourceField(IntEnum):
    TAGS = 19
    URL = 20
    NAME = 21
    ENABLED = 23
    ID = 24


class PackField(IntEnum):
    STORES = 13
    NAME = 22
    EDITOR_DATA = 23
    PROFILE_29 = 29
    DEPENDENCIES = 30
    PROFILE_35 = 35
    PROFILE_36 = 36


class StoreField(IntEnum):
    PROFILE_19 = 19
    NAME = 20
    RESOURCE_GROUPS = 21
    PROFILE_24 = 24
    PROFILE_28 = 28
    PROFILE_29 = 29


class ProjectField(IntEnum):
    NAMESPACE = 20
    NAME = 21
    DESCRIPTION = 22
    AUTHOR = 23
    PROFILE_24 = 24
    PROFILE_25 = 25
    PACKS = 26
    THUMBNAIL = 30
    PROFILE_31 = 31
    PROFILE_39 = 39
    PROFILE_40 = 40
    ID = 42


class NodeField(IntEnum):
    SLOT = 0
    FUNCTION = 1
    CHILDREN = 2
    ENABLED = 3
    DATA_TYPE = 5
    LIST_PROFILE = 6
    IDENTITY = 7
    VALUE = 20
    LIST_KIND = 21


class SettingsField(IntEnum):
    CONTEXT = 0
    ONCE = 2
    ENABLED = 3
    ACTIVE = 4
    COMMENT = 5
    EVENTS = 11
    CONDITIONS = 12
    ACTIONS = 13
    SETUPS = 14


class DataType(IntEnum):
    EVENT = 0
    CONDITION = 1
    SETUP = 2
    ACTION = 3
    DATA_LIST = 4
    COMPARISON = 7
    INTEGER_PRESET = 9
    INTEGER = 10
    BOOLEAN_PRESET = 11
    BOOLEAN = 12
    HEX_POSITION = 15
    STRING_PRESET = 18
    STRING = 19
    VARIABLE_POOL = 25
    VARIABLE_NAME_PRESET = 26
    VARIABLE_NAME = 27
    VARIABLE_VALUE = 28
    VARIABLE_LIST = 29
    RESOURCE_LINK = 31
    ENTITY = 33
    UNIT = 34
    UNIT_DATA = 36
    PLAYER = 42
    SECTOR = 44
    SIDE = 48
    STACK = 49
    STRUCTURE = 50
    PLAYER_RELATION = 55
    RACE = 71
    STORY_EVENT = 78
    STORY_EVENT_RESOURCE = 79
    DIPLOMATIC_STATE_RESOURCE = 105
    TOKEN_DEFINITION = 108
    SPECIAL_OPERATION_RESOURCE = 116
    LOCALIZED_STRING_LINK = 132
    LOCALIZED_STRING_LINK_PRESET = 133
    SPECIAL_OPERATION = 134


class ListKind(IntEnum):
    EVENTS = 0
    CONDITIONS = 1
    SETUPS = 2
    ACTIONS = 3


class ComparisonOperator(IntEnum):
    GREATER = 10
    EQUAL = 12


class EventFunction(IntEnum):
    NEW_ROUND = 3
    NEW_TURN = 5
    VICTORIOUS = 19


class ConditionFunction(IntEnum):
    ALL = 0
    ANY = 1
    INTEGER = 2
    BOOLEAN = 4


class IntegerFunction(IntEnum):
    PRESET = 0
    CURRENT_ROUND = 4
    TOKEN_COUNT = 64


class BooleanFunction(IntEnum):
    PRESET = 0
    VARIABLE_EXISTS = 2
    PLAYER_HAS_PROPERTY = 4
    PLAYER_IS_VALID = 6
    PLAYER_IS_AI = 9
    RACE_IS_VALID = 46
    RACE_HAS_TRANSFORMATION = 155


class PlayerFunction(IntEnum):
    ITERATOR = 2
    TRIGGERING = 10
    VICTORIOUS = 13


class RaceFunction(IntEnum):
    OF_PLAYER = 4


class ActionFunction(IntEnum):
    IF_THEN = 0
    FOR_EACH = 2
    SET_VARIABLE = 6
    ADD_PROPERTY = 165
    ADD_TRANSFORMATION = 217
    GIVE_TOKEN = 426
    LOG = 468
    HIDE_TOKEN_DEFINITION = 471


class VariablePoolFunction(IntEnum):
    PLAYER = 2


class VariableNameFunction(IntEnum):
    PRESET = 0


class VariableValueFunction(IntEnum):
    INTEGER = 3


class VariableListFunction(IntEnum):
    ALL_PLAYERS = 32


class TokenField(IntEnum):
    NAME = 1
    DESCRIPTION = 2
    VALUE = 9
    TEXT_ICON = 10
    PROPERTIES = 12
    ICON = 13
    LORE = 16
    FORGE_DESCRIPTION = 17
    TYPE = 18
    TAGS = 19
    ALWAYS_VISIBLE = 20
    SHOW_OPERATION = 21


class AscensionField(IntEnum):
    NAME = 0
    DESCRIPTION = 1
    ICON = 2
    UNIT_PROPERTIES = 3
    AVAILABILITY = 4
    HERO_SKILLS = 5


class HeroSkillField(IntEnum):
    NAME = 1
    DESCRIPTION = 2
    ICON = 3
    AI_PRIORITY = 6
    SIDE_PROPERTIES = 17


class HeroSkillNormalField(IntEnum):
    GROUP = 6
