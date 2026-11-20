# Authoring API

Import the public API from `aow4modkit`. See [functions.md](functions.md) for the
serialized signatures and descriptions behind the wrappers.

## Projects and triggers

`ModProject(name, folder, version, author, mod_id, ...)` holds the source
definition. `add_trigger(Trigger(...))` registers an owned global trigger.
`project.plan()` validates and compiles in memory. `build(project, output)`
writes the artifact directory, reports and ZIP; it returns a `BuildResult`.
Use `package=False` to omit the ZIP.

Important optional project fields:

| Field | Purpose |
|---|---|
| `description`, `tags` | Launcher metadata |
| `messages` | Singular English localization entries |
| `thumbnail` | Existing PNG path; source-relative paths are recommended |
| `requires` | Explicit DLC requirements in addition to used-reference requirements |
| `compatibility_notes` | Author notes copied to the compatibility report |
| `readme`, `release_notes`, `workshop_description` | Text files beside the installable folder |
| `workshop_id` | Bookkeeping in the build report; not an upload operation |

`Trigger(key, events, actions, conditions=(), once=True, comment="")` accepts
ordinary lists or tuples. Stable keys generate stable resource IDs from the
project UUID. Resource index URLs are rebuilt for the current order.

For `add_resource`, owned references, pinned IDs, player loops and persistent
variables, see [ascension recipes](ascension-recipes.md).

## Expressions

Expressions describe native operations, not values evaluated by Python:

```python
player = players.triggering()
is_ai = players.is_ai(player)
first_round = core.current_round().equals(1)
```

Do not write `if is_ai:` or `current_round == 1` in Python. Use
`actions.when(is_ai, then=[...])`, `.equals(...)`, and `conditions.all/any(...)`.
Converting an expression to a Python bool raises an explanatory error.

Wrappers validate parameter types at construction, and the compiler validates
them again. `players.is_ai(core.current_round())` is rejected before file output.
Resource kinds are checked when catalogs declare them, but raw links alone do
not prove engine class semantics.

## Events and context

- `events.new_turn()`, `events.new_round()`, `events.victorious()`
- `players.triggering()` reads the current event's player.
- `players.victorious()` reads the winner and belongs with the victorious event.
- `races.of_player(player)` reads the founding race.

An event-specific getter is meaningful only in its valid native context. The
current API checks types, not a complete static proof of event-context safety.

## Guard invalid references explicitly

Do not depend on native top-level condition lists short-circuiting:

```python
player = players.triggering()
race = races.of_player(player)
safe_action = actions.when(players.is_valid(player), then=[
    actions.when(races.is_valid(race), then=[
        actions.log("Player and race are valid.")
    ])
])
```

The nested branch ensures the inner operation is reached only after the outer
condition passes. A Python variable such as `race` stores an expression tree,
not a dereferenced live race at build time.

## Actions and side effects

`actions.log(message)` writes diagnostics, not UI. `actions.add_transformation`
applies directly without a cast or cost. `actions.give_token` can invoke native
artifact acquisition callbacks. `actions.hide_token` alone does not guarantee
that every notification is hidden. These differences are documented because
they materially affect game design.

`once=True` is global trigger deactivation after a successful firing. It does
not automatically track a separate flag for every player.

## Low-level API

The wider typed registry is available as `invoke(function_name, **arguments)`.
Embedded event scripts, dialog choices, static preservation and spell recipes
are described in [strategic recipes](strategic-recipes.md).

`formats.binary.FieldTable`, `formats.rpk.ResourceRecord/ResourcePack` and
`formats.acp.ContentProject` are available for format inspection and supported
extension work. They retain unknown field bytes instead of manufacturing a
semantic meaning. Arbitrary class authoring is not made safe merely by putting
bytes in a container. Keep unknown classes out of high-level recipes until
their schema is documented and verified.

## Typed native static values

[Native static values](native-static-values.md) covers targeter bindings, requisite lists,
army conditions, empty text contexts and atlas region/render parameters added in local
0.1.0a4.dev3. These replace the nine opaque static fields in the Donate export.

## Typed text contexts

[Text contexts](text-contexts.md) documents LocalizedText with TextContext, layout styles
and TextSubstitution. Generated resource and notification text modules contain readable
API values rather than serialized context payloads. Legacy byte contexts still compile.

## Inverse ascension recipes

[Ascension-resource export](ascension-python-export.md) documents full-pack export
through TagBook, HiddenArtifactMarker, AscensionTrait and HeroSkill, including owned
tag references and strict default/topology validation added in local dev5.
