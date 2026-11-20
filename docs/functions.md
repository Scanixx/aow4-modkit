# Supported trigger functions

Generated from `schema.FUNCTIONS`. This is a subset, not the full engine API.

## `actions.add_property`

Add a side-property resource to a player.

Serialized function: `3:165`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | property | RESOURCE_LINK |

## `actions.add_transformation`

Apply directly to a race, without casting or charging spell costs. Use a racial transformation resource.

Serialized function: `3:217`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | race | RACE |
| 2 | transformation | RESOURCE_LINK |

## `actions.create_event`

Trigger a Story Event for a Player.

Serialized function: `3:96`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | event | STORY_EVENT_RESOURCE |
| 2 | player | PLAYER |

## `actions.delete`

Delete a variable from the given pool.

Serialized function: `3:7`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | variable_pool | VARIABLE_POOL |
| 2 | variable_name | VARIABLE_NAME |

## `actions.for_each`

Execute a body for each list element; iterator depth 0 selects the current item.

Serialized function: `3:2`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | items | VARIABLE_LIST |
| 2 | body | DATA_LIST |

## `actions.give_token`

Give a token; native acquisition notifications may be generated.

Serialized function: `3:426`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | token | RESOURCE_LINK |
| 3 | amount | INTEGER |

## `actions.hide_token`

Remove explicit token visibility; this alone does not suppress all acquisition UI.

Serialized function: `3:471`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | token | TOKEN_DEFINITION |

## `actions.log`

Write a native diagnostic log message, not an on-screen notification.

Serialized function: `3:468`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | message | STRING |

## `actions.when`

Branch explicitly; use nesting to guard potentially invalid references.

Serialized function: `3:0`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | conditions | DATA_LIST |
| 2 | then | DATA_LIST |
| 3 | otherwise | DATA_LIST |

## `comparisons.diplomatic_state_resource`

Native Comparison.DiplomaticStateResource expression.

Serialized function: `1:42`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | left | DIPLOMATIC_STATE_RESOURCE |
| 2 | operator | COMPARISON |
| 3 | right | DIPLOMATIC_STATE_RESOURCE |

## `comparisons.integer`

Native Comparison.Integer expression.

Serialized function: `1:2`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | left | INTEGER |
| 2 | operator | COMPARISON |
| 3 | right | INTEGER |

## `comparisons.side`

Native Comparison.Side expression.

Serialized function: `1:18`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | left | SIDE |
| 2 | operator | COMPARISON |
| 3 | right | SIDE |

## `comparisons.special_operation_resource`

Native Comparison.SpecialOperationResource expression.

Serialized function: `1:51`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | left | SPECIAL_OPERATION_RESOURCE |
| 2 | operator | COMPARISON |
| 3 | right | SPECIAL_OPERATION_RESOURCE |

## `comparisons.structure`

Native Comparison.Structure expression.

Serialized function: `1:20`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | left | STRUCTURE |
| 2 | operator | COMPARISON |
| 3 | right | STRUCTURE |

## `conditions.all`

Require all nested conditions.

Serialized function: `1:0`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | conditions | DATA_LIST |

## `conditions.any`

Require at least one nested condition.

Serialized function: `1:1`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | conditions | DATA_LIST |

## `conditions.boolean_equals`

Compare two booleans for equality.

Serialized function: `1:4`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | left | BOOLEAN |
| 2 | operator | COMPARISON |
| 3 | right | BOOLEAN |

## `conditions.integer_equals`

Compare two integers for equality.

Serialized function: `1:2`. Result: `CONDITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | left | INTEGER |
| 2 | operator | COMPARISON |
| 3 | right | INTEGER |

## `core.current_round`

Read the current round number.

Serialized function: `10:4`. Result: `INTEGER`.

## `diplomacy.player_relation`

Retrieve the Diplomatic State Resource of a Player Relation.

Serialized function: `105:2`. Result: `DIPLOMATIC_STATE_RESOURCE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player_relation | PLAYER_RELATION |

## `diplomacy.resource_link`

Retrieve a Diplomatic State Resource from a Resource Link.

Serialized function: `105:1`. Result: `DIPLOMATIC_STATE_RESOURCE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | resource_link | RESOURCE_LINK |

## `entities.structure`

Retrieve a Structure as an Entity.

Serialized function: `33:7`. Result: `ENTITY`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | structure | STRUCTURE |

## `entities.unit`

Retrieve a Unit as an Entity.

Serialized function: `33:5`. Result: `ENTITY`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `entities.variable`

Retrieve an Entity value from a variable.

Serialized function: `33:1`. Result: `ENTITY`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | variable_value | VARIABLE_VALUE |

## `event_resources.resource_link`

Retrieve a Story Event Resource from a Resource Link.

Serialized function: `79:1`. Result: `STORY_EVENT_RESOURCE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | resource_link | RESOURCE_LINK |

## `events.compatibility_validation`

The system runs compatibility validation process.

Serialized function: `0:2`. Result: `EVENT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | data_list | DATA_LIST |

## `events.new_round`

Run when a new round starts.

Serialized function: `0:3`. Result: `EVENT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | conditions | DATA_LIST |

## `events.new_turn`

Run when a new turn starts.

Serialized function: `0:5`. Result: `EVENT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | conditions | DATA_LIST |

## `events.specific_spawn`

A Player tries to check if this Event should be spawned.

Serialized function: `0:73`. Result: `EVENT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | data_list | DATA_LIST |

## `events.victorious`

Run when a player becomes victorious.

Serialized function: `0:19`. Result: `EVENT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | conditions | DATA_LIST |

## `integers.variable`

Retrieve an Integer value from a variable.

Serialized function: `10:1`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | variable_value | VARIABLE_VALUE |

## `players.all`

Read all players for a list loop.

Serialized function: `29:32`. Result: `VARIABLE_LIST`.

## `players.cast_spell`

A player casts a spell.

Serialized function: `0:89`. Result: `EVENT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | data_list | DATA_LIST |

## `players.condition`

Retrieve a List of Players matching the given Conditions.

Serialized function: `29:33`. Result: `VARIABLE_LIST`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | data_list | DATA_LIST |

## `players.has_property`

Check a side-property resource on the player.

Serialized function: `12:4`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | property | RESOURCE_LINK |

## `players.has_skill_researched`

Check if a Player has researched the given Skill.

Serialized function: `12:108`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | resource_link | RESOURCE_LINK |

## `players.is_ai`

Check whether the player is AI-controlled.

Serialized function: `12:9`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |

## `players.is_lord`

Check if a Player is a Lord Player.

Serialized function: `12:10`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |

## `players.is_valid`

Check a player reference before dereferencing it.

Serialized function: `12:6`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |

## `players.iterator`

Read a player from the selected loop depth (0 = current loop).

Serialized function: `42:2`. Result: `PLAYER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | depth | INTEGER |

## `players.show_todo_event_at_position`

Show a custom Todo Event in a Player's Event List, optionally using variables from the given pool.

Serialized function: `3:522`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | title | LOCALIZED_STRING_LINK |
| 3 | body | LOCALIZED_STRING_LINK |
| 4 | icon | RESOURCE_LINK |
| 5 | hover_icon | RESOURCE_LINK |
| 6 | position | HEX_POSITION |
| 7 | variables | VARIABLE_POOL |

## `players.side`

Retrieve the Player of a Side.

Serialized function: `42:5`. Result: `PLAYER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | side | SIDE |

## `players.story_event`

Retrieve the Player of a Story Event. Only valid in Story Event Scripts.

Serialized function: `42:9`. Result: `PLAYER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | story_event | STORY_EVENT |

## `players.token_count`

Count a token definition held by a player.

Serialized function: `10:64`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | token | TOKEN_DEFINITION |

## `players.triggering`

Read the player from the current event context.

Serialized function: `42:10`. Result: `PLAYER`.

## `players.unlock_research`

Instantly complete research on the given skill for a Player.

Serialized function: `3:72`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |
| 2 | resource_link | RESOURCE_LINK |

## `players.victorious`

Read the winner; use with the victorious event.

Serialized function: `42:13`. Result: `PLAYER`.

## `pools.local`

Retrieve the Local Variable Pool.

Serialized function: `25:4`. Result: `VARIABLE_POOL`.

## `pools.story_event`

Retrieve the Variable Pool of a Story Event.

Serialized function: `25:3`. Result: `VARIABLE_POOL`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | story_event | STORY_EVENT |

## `positions.special_operation`

Retrieve the Position of a Special Operation.

Serialized function: `15:19`. Result: `HEX_POSITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | special_operation | SPECIAL_OPERATION |

## `positions.unit`

Retrieve the Position of a Unit.

Serialized function: `15:9`. Result: `HEX_POSITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `positions.variable`

Retrieve a Position value from a variable.

Serialized function: `15:3`. Result: `HEX_POSITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | variable_value | VARIABLE_VALUE |

## `races.has_transformation`

Read the applied transformation list; not spell knowledge or artifact ownership. Suppression is not checked separately.

Serialized function: `12:155`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | race | RACE |
| 2 | transformation | RESOURCE_LINK |

## `races.is_valid`

Check a race reference before dereferencing it.

Serialized function: `12:46`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | race | RACE |

## `races.of_player`

Get the player's founding race.

Serialized function: `71:4`. Result: `RACE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |

## `relations.player`

Retrieve the Relation between two Players.

Serialized function: `55:1`. Result: `PLAYER_RELATION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | source | PLAYER |
| 2 | target | PLAYER |

## `sectors.hex_pos`

Retrieve the Sector at the given Position.

Serialized function: `44:5`. Result: `SECTOR`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | hex_pos | HEX_POSITION |

## `sides.is_lord`

Check if a Side belongs to a Lord Player.

Serialized function: `12:60`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | side | SIDE |

## `sides.player`

Retrieve the Side of a Player.

Serialized function: `48:6`. Result: `SIDE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |

## `sides.stack`

Retrieve the Side of a Stack.

Serialized function: `48:11`. Result: `SIDE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | stack | STACK |

## `sides.structure`

Retrieve the Side that owns a Structure.

Serialized function: `48:12`. Result: `SIDE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | structure | STRUCTURE |

## `sides.unit`

Retrieve the Side of a Unit.

Serialized function: `48:9`. Result: `SIDE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `sides.variable`

Retrieve a Side value from a variable.

Serialized function: `48:1`. Result: `SIDE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | variable_value | VARIABLE_VALUE |

## `spell_resources.resource_link`

Retrieve a Special Operation Resource from a Resource Link.

Serialized function: `116:0`. Result: `SPECIAL_OPERATION_RESOURCE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | resource_link | RESOURCE_LINK |

## `spell_resources.triggering`

Native Event.Triggering expression.

Serialized function: `116:1`. Result: `SPECIAL_OPERATION_RESOURCE`.

## `spells.triggering`

Native Event.Triggering expression.

Serialized function: `134:1`. Result: `SPECIAL_OPERATION`.

## `stacks.has_unit`

Check if a Stack contains the given Unit.

Serialized function: `12:17`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | stack | STACK |
| 2 | unit | UNIT |

## `stacks.hex_pos`

Retrieve the Stack at the given Position.

Serialized function: `49:5`. Result: `STACK`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | hex_pos | HEX_POSITION |

## `stacks.is_valid`

Check if a Stack is valid (not null).

Serialized function: `12:18`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | stack | STACK |

## `stacks.set_side`

Change the Side of a Stack.

Serialized function: `3:76`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | stack | STACK |
| 2 | side | SIDE |

## `stacks.unit`

Retrieve the Stack containing a Unit.

Serialized function: `49:6`. Result: `STACK`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `stacks.unit_count`

Retrieve the number of Units in a Stack.

Serialized function: `10:59`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | stack | STACK |

## `story_events.this`

Retrieve the current Story Event this script is running on.

Serialized function: `78:1`. Result: `STORY_EVENT`.

## `structures.domain_structure`

Retrieve the Domain Structure of a Sector. Typically a City or Outpost.

Serialized function: `50:31`. Result: `STRUCTURE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | sector | SECTOR |

## `structures.entity`

Retrieve an Entity as a Structure.

Serialized function: `50:26`. Result: `STRUCTURE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | entity | ENTITY |

## `structures.has_vision`

Check if a Player has vision on a Structure.

Serialized function: `12:181`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | structure | STRUCTURE |
| 2 | player | PLAYER |

## `structures.is_city`

Check if a Structure is a City.

Serialized function: `12:31`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | structure | STRUCTURE |

## `structures.is_valid`

Check if a Structure is valid (not null).

Serialized function: `12:30`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | structure | STRUCTURE |

## `text.localized_link`

Set a Localized String Link value manually.

Serialized function: `132:0`. Result: `LOCALIZED_STRING_LINK`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | localized_string_link_preset | LOCALIZED_STRING_LINK_PRESET |

## `tokens.definition`

Resolve a token definition from a resource link.

Serialized function: `108:1`. Result: `TOKEN_DEFINITION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | token | RESOURCE_LINK |

## `unit_data.unit`

Retrieve the Unit Data of a Unit.

Serialized function: `36:3`. Result: `UNIT_DATA`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.entity`

Retrieve an Entity as a Unit.

Serialized function: `34:24`. Result: `UNIT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | entity | ENTITY |

## `units.hit_points`

Retrieve the number of Hit Points a Unit has.

Serialized function: `10:35`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.hit_points_max`

Retrieve the maximum number of Hit Points a Unit can have.

Serialized function: `10:36`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.is_dead`

Check if a Unit is dead.

Serialized function: `12:70`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.is_hero`

Check if a Unit is a Hero.

Serialized function: `12:76`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.is_leader`

Check if a Unit is a Leader.

Serialized function: `12:77`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.is_valid`

Check if a Unit is valid (not null).

Serialized function: `12:35`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.move_points`

Retrieve the number of Move Points a Unit has.

Serialized function: `10:33`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.move_points_max`

Retrieve the maximum number of Move Points a Unit can have.

Serialized function: `10:34`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `units.set_side`

Change the Side of a Unit.

Serialized function: `3:203`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |
| 2 | side | SIDE |

## `units.stack_slot`

Retrieve the Unit in the given Slot of a Stack.

Serialized function: `34:20`. Result: `UNIT`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | stack | STACK |
| 2 | slot | INTEGER |

## `units.unit_rank`

Retrieve the Rank of a Unit.

Serialized function: `10:68`. Result: `INTEGER`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit | UNIT |

## `values.bool`

Create a Variable Value from a Boolean.

Serialized function: `28:4`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | boolean | BOOLEAN |

## `values.entity`

Create a Variable Value from an Entity.

Serialized function: `28:10`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | entity | ENTITY |

## `values.hex_pos`

Create a Variable Value from a Position.

Serialized function: `28:8`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | hex_pos | HEX_POSITION |

## `values.name`

Retrieve a Variable Value by Name from a Variable Pool.

Serialized function: `28:0`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | variable_pool | VARIABLE_POOL |
| 2 | variable_name | VARIABLE_NAME |

## `values.player`

Create a Variable Value from a Player.

Serialized function: `28:12`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |

## `values.side`

Create a Variable Value from a Side.

Serialized function: `28:13`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | side | SIDE |

## `values.unit_data`

Create a Variable Value from Unit Data.

Serialized function: `28:21`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | unit_data | UNIT_DATA |

## `variables.exists`

Check whether a named variable exists in a pool.

Serialized function: `12:2`. Result: `BOOLEAN`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | pool | VARIABLE_POOL |
| 2 | name | VARIABLE_NAME |

## `variables.integer`

Wrap an integer as a variable value.

Serialized function: `28:3`. Result: `VARIABLE_VALUE`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | value | INTEGER |

## `variables.name`

Create a named variable reference.

Serialized function: `27:0`. Result: `VARIABLE_NAME`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | name | VARIABLE_NAME_PRESET |

## `variables.player_pool`

Get persistent scenario variables belonging to a player.

Serialized function: `25:2`. Result: `VARIABLE_POOL`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | player | PLAYER |

## `variables.set`

Create or replace a variable in its pool.

Serialized function: `3:6`. Result: `ACTION`.

| Slot | Parameter | Type |
|---|---|---|
| 1 | pool | VARIABLE_POOL |
| 2 | name | VARIABLE_NAME |
| 3 | value | VARIABLE_VALUE |

