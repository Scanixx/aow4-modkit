# Ascension recipes and existing-mod migration

The 0.1.0a2 preview adds public resource recipes for the observed AoW4 2.3 profile.
They do not clone an old RPK or require native executable analysis at build time.
Unknown structural defaults remain explicitly documented in
`resource_schemas/ascension_2_3.json`, separate from author-supplied content.

## Public recipes

| Recipe | Purpose |
|---|---|
| `TagBook` / `TagDefinition` | Define owned eligibility tags with stable UUIDs |
| `HiddenArtifactMarker` | Artifact-type eligibility tag, no grants, price or icon |
| `AscensionTrait` | Victory selection entry gated by a tag, linking hero skills |
| `HeroSkill` | Observed normal hero-skill subtype with side-property grants |
| `SideProperty` | Generic inert side-property marker |
| `LocalizedText` | Catalog key and optional preserved formatter context |

Use `project.add_resource(recipe)`. `project.ref(key, kind=...)` creates an owned
forward reference resolved at build time. Internal references do not add the
project's own pack as an external dependency. Missing keys, conflicting IDs and
known kind mismatches stop validation.

```python
from uuid import UUID
from aow4modkit import TagBook, TagDefinition, SideProperty

book = TagBook(
    key="eligibility", root="MyMod",
    root_guid=UUID("b1ce1f69-ec65-430d-98d2-a578d6cd53a4"),
    tags=(TagDefinition("Example", UUID("058a64b6-164a-4ed2-b5ad-d653a0fc2ec4")),),
)
project.add_resource(book)
project.add_resource(SideProperty(key="inherited_marker"))
tag = book.tag("Example")
marker = project.ref("inherited_marker", kind="side_property")
```

Choose your own stable UUIDs for a new mod. The sample UUIDs are examples only.
Use catalog refs for a hero skill's icon, AI priority, group and side properties.
Recipes author links to these resources; they do not embed the supplying DLC.

## Preserve an existing mod's identities

Each recipe and `Trigger` accepts `resource_id=` and `name=`. Pin the actual IDs
when migrating released content. Regenerating IDs from new symbolic keys would
break old saved references even if the definitions look similar.

`project.definition_order` lists all recipe/trigger keys in their required order.
This preserves index URLs where necessary. `pack_name`, `catalog_name`,
`namespace` and `short_description` can preserve existing filenames/metadata.
The mod UUID and Workshop ID remain independent identities.

## Player loops and state

```python
from aow4modkit import actions, players, variables

player = players.iterator()
pool = variables.player_pool(player)
body = actions.guard([
    players.is_valid(player),
    players.is_ai(player),
    variables.exists(pool, "MYMOD_DONE_V1").equals(False),
], then=[variables.set_integer(pool, "MYMOD_DONE_V1", 1)])
loop = actions.for_each_player(body)
```

Nested guards protect invalid references; a flat native condition list is not
assumed to short-circuit. Variable names are persistent scenario-state keys.
Preserve them across updates if existing saved initialization state matters.

## Localized formatter context

Most new definitions can use `LocalizedText("MYMOD@NAME")`. Migration can supply
`context=` bytes containing the old localized-link formatter metadata, with the
key replaced by the new declaration. This retains parameter/link metadata and
avoids silently changing fallback formatting. It is not translated text or a
complete native-resource snapshot. Source projects should document such data;
it is an advanced compatibility feature, not normal author-facing boilerplate.

## Equivalence checks

Do not demand binary equality when field-table encoding or node cache identities
change. Compare typed fields, links, tag logic, localized parameters, node
operations/slots/order, enable/once flags and persistent state names. Retain exact
checks for unknown fields and gameplay data that should not change.

More Secret Ascension Skills is the first local integration using these recipes.
Its independent audit compares all eleven definitions against the original 0.4
release and replays the nine victory and sixteen AI serialized-graph scenarios.
This is offline equivalence evidence, not a replacement for game/save/Pantheon
testing. The original released archive is retained unchanged.
