"""Experimental Python mod authoring for Age of Wonders 4 2.3.x.

Python runs at build time; the game receives ACP/RPK/MO/metadata only.
"""
from .api import actions, conditions, core, events, players, races, variables
from .compiler import Trigger, Script
from .content import ContentCatalog
from .expressions import Expr, ResourceRef, OwnedResourceRef, invoke, comparison, localized_link, literal, group as sequence
from .constants import ListKind, ComparisonOperator
from .strategic_resources import (PreservedParameter, DialogChoice, StrategicArmySpell,
                                 ArmyTargeter, ResearchSkill, SpellUnlockProperty, TextureAtlasIcon, StoryEvent)
from .resources import (ResourceDefinition, LocalizedText, TagDefinition, TagRef,
                        TagBook, HiddenArtifactMarker, AscensionTrait, HeroSkill, SideProperty)
from .project import ModProject, BuildResult, build
from .compatibility import DlcRequirement, TARGET_GAME_SERIES
from .errors import ModKitError, FormatError, ValidationError
from .profiles import GameProfile, DEFAULT_PROFILE, get_profile

__version__ = "0.1.0a3"
__all__ = ["ModProject", "Trigger", "Expr", "ResourceRef", "ContentCatalog",
           "DlcRequirement", "TARGET_GAME_SERIES", "actions", "conditions", "core",
           "events", "players", "races", "build", "BuildResult",
           "ModKitError", "FormatError", "ValidationError", "GameProfile", "DEFAULT_PROFILE", "get_profile"]
__all__ += ["OwnedResourceRef", "ResourceDefinition", "LocalizedText", "TagDefinition", "TagRef",
            "TagBook", "HiddenArtifactMarker", "AscensionTrait", "HeroSkill", "SideProperty", "variables"]
__all__ += ["Script", "invoke", "comparison", "localized_link", "literal", "sequence", "ListKind", "ComparisonOperator",
            "PreservedParameter", "DialogChoice", "StrategicArmySpell", "ArmyTargeter", "ResearchSkill",
            "SpellUnlockProperty", "TextureAtlasIcon", "StoryEvent"]
