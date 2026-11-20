"""Small documented function registry used by authoring, validation and docs.

Only these signatures are exposed. Unsupported engine functions must not be
guessed from a similar name. IDs were checked against the local trigger metadata
and existing data graphs; see compatibility documentation for runtime limits.
"""
from dataclasses import dataclass
from importlib.resources import files
import json
from .constants import (
    DataType as T, EventFunction as E, ConditionFunction as C,
    IntegerFunction as I, BooleanFunction as B, PlayerFunction as P,
    RaceFunction as R, ActionFunction as A,
    VariablePoolFunction, VariableNameFunction, VariableValueFunction, VariableListFunction,
)


@dataclass(frozen=True)
class Parameter:
    name: str
    data_type: T


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    data_type: T
    function_id: int
    parameters: tuple[Parameter, ...]
    description: str


def _spec(function_name, kind, ident, description, **parameters):
    return FunctionSpec(function_name, kind, int(ident),
                        tuple(Parameter(k, v) for k, v in parameters.items()), description)


FUNCTIONS = {s.name: s for s in [
    _spec("events.new_round", T.EVENT, E.NEW_ROUND, "Run when a new round starts.", conditions=T.DATA_LIST),
    _spec("events.new_turn", T.EVENT, E.NEW_TURN, "Run when a new turn starts.", conditions=T.DATA_LIST),
    _spec("events.victorious", T.EVENT, E.VICTORIOUS, "Run when a player becomes victorious.", conditions=T.DATA_LIST),
    _spec("conditions.all", T.CONDITION, C.ALL, "Require all nested conditions.", conditions=T.DATA_LIST),
    _spec("conditions.any", T.CONDITION, C.ANY, "Require at least one nested condition.", conditions=T.DATA_LIST),
    _spec("conditions.integer_equals", T.CONDITION, C.INTEGER, "Compare two integers for equality.", left=T.INTEGER, operator=T.COMPARISON, right=T.INTEGER),
    _spec("conditions.boolean_equals", T.CONDITION, C.BOOLEAN, "Compare two booleans for equality.", left=T.BOOLEAN, operator=T.COMPARISON, right=T.BOOLEAN),
    _spec("core.current_round", T.INTEGER, I.CURRENT_ROUND, "Read the current round number."),
    _spec("players.token_count", T.INTEGER, I.TOKEN_COUNT, "Count a token definition held by a player.", player=T.PLAYER, token=T.TOKEN_DEFINITION),
    _spec("tokens.definition", T.TOKEN_DEFINITION, 1, "Resolve a token definition from a resource link.", token=T.RESOURCE_LINK),
    _spec("players.triggering", T.PLAYER, P.TRIGGERING, "Read the player from the current event context."),
    _spec("players.iterator", T.PLAYER, P.ITERATOR, "Read a player from the selected loop depth (0 = current loop).", depth=T.INTEGER),
    _spec("players.all", T.VARIABLE_LIST, VariableListFunction.ALL_PLAYERS, "Read all players for a list loop."),
    _spec("players.victorious", T.PLAYER, P.VICTORIOUS, "Read the winner; use with the victorious event."),
    _spec("players.is_valid", T.BOOLEAN, B.PLAYER_IS_VALID, "Check a player reference before dereferencing it.", player=T.PLAYER),
    _spec("players.is_ai", T.BOOLEAN, B.PLAYER_IS_AI, "Check whether the player is AI-controlled.", player=T.PLAYER),
    _spec("players.has_property", T.BOOLEAN, B.PLAYER_HAS_PROPERTY, "Check a side-property resource on the player.", player=T.PLAYER, property=T.RESOURCE_LINK),
    _spec("races.of_player", T.RACE, R.OF_PLAYER, "Get the player's founding race.", player=T.PLAYER),
    _spec("races.is_valid", T.BOOLEAN, B.RACE_IS_VALID, "Check a race reference before dereferencing it.", race=T.RACE),
    _spec("races.has_transformation", T.BOOLEAN, B.RACE_HAS_TRANSFORMATION, "Read the applied transformation list; not spell knowledge or artifact ownership. Suppression is not checked separately.", race=T.RACE, transformation=T.RESOURCE_LINK),
    _spec("actions.when", T.ACTION, A.IF_THEN, "Branch explicitly; use nesting to guard potentially invalid references.", conditions=T.DATA_LIST, then=T.DATA_LIST, otherwise=T.DATA_LIST),
    _spec("actions.add_property", T.ACTION, A.ADD_PROPERTY, "Add a side-property resource to a player.", player=T.PLAYER, property=T.RESOURCE_LINK),
    _spec("actions.add_transformation", T.ACTION, A.ADD_TRANSFORMATION, "Apply directly to a race, without casting or charging spell costs. Use a racial transformation resource.", race=T.RACE, transformation=T.RESOURCE_LINK),
    _spec("actions.give_token", T.ACTION, A.GIVE_TOKEN, "Give a token; native acquisition notifications may be generated.", player=T.PLAYER, token=T.RESOURCE_LINK, amount=T.INTEGER),
    _spec("actions.hide_token", T.ACTION, A.HIDE_TOKEN_DEFINITION, "Remove explicit token visibility; this alone does not suppress all acquisition UI.", player=T.PLAYER, token=T.TOKEN_DEFINITION),
    _spec("actions.log", T.ACTION, A.LOG, "Write a native diagnostic log message, not an on-screen notification.", message=T.STRING),
    _spec("actions.for_each", T.ACTION, A.FOR_EACH, "Execute a body for each list element; iterator depth 0 selects the current item.", items=T.VARIABLE_LIST, body=T.DATA_LIST),
    _spec("variables.player_pool", T.VARIABLE_POOL, VariablePoolFunction.PLAYER, "Get persistent scenario variables belonging to a player.", player=T.PLAYER),
    _spec("variables.name", T.VARIABLE_NAME, VariableNameFunction.PRESET, "Create a named variable reference.", name=T.VARIABLE_NAME_PRESET),
    _spec("variables.integer", T.VARIABLE_VALUE, VariableValueFunction.INTEGER, "Wrap an integer as a variable value.", value=T.INTEGER),
    _spec("variables.exists", T.BOOLEAN, B.VARIABLE_EXISTS, "Check whether a named variable exists in a pool.", pool=T.VARIABLE_POOL, name=T.VARIABLE_NAME),
    _spec("variables.set", T.ACTION, A.SET_VARIABLE, "Create or replace a variable in its pool.", pool=T.VARIABLE_POOL, name=T.VARIABLE_NAME, value=T.VARIABLE_VALUE),
]}

# Larger observed signature subsets are data, still validated by the same
# typed registry and documented by the same reference generator.
for _row in json.loads(files("aow4modkit").joinpath(
        "function_schemas", "strategic_2_3.json").read_text(encoding="utf-8"))["functions"]:
    if _row["name"] in FUNCTIONS:
        raise ValueError("Duplicate registered function name: " + _row["name"])
    FUNCTIONS[_row["name"]] = FunctionSpec(
        _row["name"], T(_row["data_type"]), _row["function_id"],
        tuple(Parameter(p["name"], T(p["data_type"])) for p in _row["parameters"]),
        _row["description"],
    )
