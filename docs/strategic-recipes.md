# Strategic spells and event dialogs

Available in 0.1.0a3 for the observed `aow4-2.3-observed-v1` profile.
These are limited, evidence-based recipes, not constructors for every spell.

## Public types

| Type | Purpose |
|---|---|
| `StrategicArmySpell` | Strategic army spell, presentation and operation links |
| `ArmyTargeter` | Observed army targeter fields and static requisites |
| `ResearchSkill` | Research entry with automatic grants and presentation |
| `SpellUnlockProperty` | Side property holding operation unlocks |
| `StoryEvent` | Event initialization and explicit dialog choices |
| `DialogChoice` | Stable list ID, text, category, action and visibility scripts |
| `TextureAtlasIcon` | Reference to an already prepared atlas region |
| `Script` | Embedded event/choice script, separate from a global `Trigger` |

Each recipe takes normal resource identity arguments (`key`, optional `name`
and `resource_id`) plus a `parameters` dictionary. Required parameter names,
field IDs and codecs are defined in `resource_schemas/strategic_2_3.json`.
Unknown or missing parameters fail validation. Names beginning with `native_`
are deliberately neutral: their full engine meaning has not been established.

The atlas recipe does not create or convert CLB files. Supply an author-owned,
already prepared CLB through `ModProject.assets`. The toolkit includes no game
textures or sample CLB from a commercial game.

## Named function calls

```python
from aow4modkit import invoke, players, variables

player = players.triggering()
pool = variables.player_pool(player)
exists = invoke("variables.exists", pool=pool, name=variables.name("DONE"))
```

`invoke(function_name, **arguments)` validates names, arity and expression types.
Python keyword order does not change native argument slots. The complete
registry has 105 named entries, including two integer-comparison names for the
same native signature. See [the generated reference](functions.md).

Expression reuse is build-time reuse only. Every occurrence produces fresh
native nodes, so storing an expression in a Python variable does not cache its
live result during gameplay.

## Embedded scripts and choices

```python
from aow4modkit import Script, DialogChoice, LocalizedText, actions

close = Script(key="choice.close", events=[], actions=[actions.log("Closed")])
visible = Script(key="choice.visible", events=[], actions=[], conditions=[])
# category must be a valid author-declared event-button resource reference.
choice = DialogChoice(list_id=0, text=LocalizedText("EXAMPLE@CLOSE"),
                      category=category, action=close, visibility=visible,
                      visibility_mode=4)
```

The last example is a fragment inside an authored event, not a complete mod.
Choice IDs are explicit and unique in 0..254. The serialized list's next free
ID is computed from the highest choice ID. `visibility_mode=4` preserves the
mode used by the verified Donate selection dialog. Other numeric modes can be
serialized, but the toolkit does not certify their UI behavior.

`Script` uses native event context 2 and can omit events. It cannot be added as
a global project trigger. Scripts compiled into one event share a node identity
allocator, preventing collisions across initialization and button scripts.

`setups=[...]` is a distinct phase. Verified action counterparts with function
IDs 0..12 are emitted as native setup nodes, including nested setup lists.
Unsupported actions in this phase fail; an action ID cannot be assumed to
identify an equivalent setup function.

`localized_link(LocalizedText(...))` supports contextual notification text.
An optional `LocalizedText.context` retains existing formatter metadata, even
when the localized link is wrapped by an outer field table.

## Explicit static preservation

`PreservedParameter(data, description)` retains a static field whose complete
schema remains unknown. A meaningful description is required. This is used for
some targeter wrappers, empty contexts and atlas rendering parameters. It must
not hide serialized executable graphs or entire resources. Independent migration
checks compare these values byte for byte.

Consequently, changing a resource ID may also require rebuilding an opaque
wrapper containing that ID. The reference walker cannot discover dependencies
inside unknown bytes. This is a documented boundary, not automatic portability.

## Assets and migration controls

`assets` maps safe relative POSIX paths to existing files. Generated file names
and case-insensitive aliases cannot be overwritten. Files are copied unchanged;
there is no image transformation or CLB generation.

`pack_filename` and `catalog_filename` retain existing on-disk filename case
while `pack_name` and `catalog_name` keep native uppercase identifiers.

An optional `dependency_manifest` preserves an explicitly audited dependency
list and order. This is intended for existing-mod migrations. It emits a warning
and reports undeclared reference-origin packs instead of silently appending them.
New projects should normally use automatically inferred dependencies.

## Verification boundary

Donate Spell 0.14 was rebuilt with these public types and compared independently
with its reference release: nine resources, 17 scripts and 8,266 executable
nodes match in meaning, with 41 offline behavior cases. Icon/atlas bytes,
localization, ACP field values, metadata and dependency order remain unchanged.
Generated node identities and field-table framing differ.

The migrated project is a separate example outside the SDK distribution because
it includes game-derived artwork. The SDK contains no dependency on that project
or its development translator. Offline comparison does not prove new engine,
save or multiplayer behavior. A rebuilt package still needs an in-game test.
