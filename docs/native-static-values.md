# Native static values in the 2.3 profile

Local development API added in 0.1.0a4.dev3. These Python objects describe RPK
data at build time. They do not run Python inside the game and do not generate
CLB atlas/image files.

## Replacement map

The observed Donate export previously preserved nine static values (761 bytes).
They now have the following public API representations:

| Resource field | Bytes | Constructor |
| --- | ---: | --- |
| Spell `targeter_binding` | 137 | `StrategicTargeterBinding` |
| Spell `empty_text_context` | 23 | `EmptyTextContext` |
| Spell `native_list_44` | 7 | `ResourceHandleList` |
| Spell `operation_tags` | 143 | `ResourceHandleList` |
| Targeter `unit_requisite_filter` | 65 | `UnitRequisiteFilter` |
| Targeter `target_conditions` | 72 | `ArmyTargetConditions` |
| Unlock property `empty_title` | 23 | `EmptyTextContext` |
| Unlock property `empty_description` | 23 | `EmptyTextContext` |
| Icon `atlas_region` | 268 | `TextureAtlasRegion` |

Byte counts describe that observed input, not fixed limits or universal sizes.
No mod-specific IDs, resource names or asset paths are embedded in the codecs.

## Usage

```python
from aow4modkit import (
    ResourceHandle, ResourceHandleList, EmptyTextContext,
    StrategicTargeterBinding, UnitRequisiteFilter,
)

# Illustrative IDs and names only; supply references from your own project.
targeters = ResourceHandleList(
    handles=(ResourceHandle(101, "Example targeter"),),
    compact=False,
)
binding = StrategicTargeterBinding(targeters=targeters, native_selector_value=1537)
empty_title = EmptyTextContext()
requisites = UnitRequisiteFilter(
    native_field_4=ResourceHandleList((ResourceHandle(102, "Example requisite"),)),
)
```

Pass these objects directly as the corresponding resource recipe parameters.
The usual `ResourcePackProject.build()` path serializes them along with the
other parameters. Older `PreservedParameter` inputs still compile unchanged.
The strict inverse exporter expects the supported named layouts and rejects
malformed data instead of reverting to an opaque payload.

`ResourceHandleList(handles=(), compact=True)` is an empty native list.
`compact` selects narrow versus wide field directories; it is a serialization
choice, not a gameplay flag. Lists preserve reference order and names. Bare
`ResourceHandle` references are intended for the explicit serialized-reference
context of `ResourcePackProject`. A `ModProject` still requires declared
references so that dependency checks have pack/DLC provenance.

Atlas values use nested constructors:

```python
from aow4modkit import (
    ResourceLink, TextureAtlasRegion, AtlasSpriteReference,
    EnvironmentReference, AtlasRenderParameters,
)

atlas = TextureAtlasRegion(
    sprite=AtlasSpriteReference("[EXAMPLE_ICONS]TXA\\0", "Example icon"),
    render_profile=ResourceLink(103, "Example profile", "[#0000000000000067]0\\0"),
    environment=EnvironmentReference("EXAMPLE.ENV", "Example"),
    render_parameters=AtlasRenderParameters(
        native_vector_0=(0.0, 0.0, 5.0), native_scalar_3=0.8,
    ),
    native_flag_54=False,
)
```

This creates a reference to an existing atlas region, not the texture atlas
itself. The referenced files/resources must be provided by the game or mod.

## Verified structure and interpretation limits

Constants are named in `aow4modkit.native_values`. Their names are descriptive
SDK labels, not claims about the engine's original C++ symbol names.

| Constant | Native class ID | Observed structure |
| --- | --- | --- |
| `HANDLE_CLASS` | `0x0040004A` | Fields 20: uint64 ID; 22: counted UTF-8 name |
| `TARGETER_BINDING_CLASS` | `0x00470221` | Targeter list in field 3; selector class field |
| `TARGETER_SELECTOR_CLASS` | `0x00471817` | uint32 selector value |
| `TEXT_CONTEXT_CLASS` | `0x00401604` | Empty formatter context nested under field 2 |
| `ARMY_CONDITIONS_CLASS` | `0x00476E8A` | Lists in 2, 3, 4, 7; uint32 values in 8 and 1 |
| `ATLAS_REGION_CLASS` | `0x040112C2` | Sprite 0; render profile 50; environment 51; render parameters 53; flag 54 |
| `ATLAS_VECTOR_CLASS` | `0x04011309` | Three float32 values in 0; one float32 value in 3 |

`UnitRequisiteFilter` contains lists in fields 3, 4 and 5. The observed use
places a hero requisite in field 4, but this alone does not prove the complete
matching rules for all three lists. Their names deliberately retain field IDs.
Likewise, selector value 1537, army values 513/1, sprite field 21 and the atlas
vector/scalar/flag have verified widths and values; their full gameplay/rendering
meaning is unverified. Do not interpret them as public engine enumerations.

The atlas path, region name, render-profile reference and environment strings
are decoded separately and editable. Float values use IEEE-754 float32 encoding.
An exported `0.800000011920929` is the exact decoded float32 value; writing
Python `0.8` encodes to the same float32 bits. Nonfinite values are rejected.

Each type provides `encode(context=None)` and `decode(raw)` for the observed
layout. The optional context resolves declared/owned references during recipe
compilation. Readers check field sets, class IDs, primitive widths, list indices
and boolean values. They reject unsupported extra fields instead of dropping
them. These types are deliberately scoped to this observed profile, not an
automatic decoder for every class or future game version.

## Evidence

All nine original static values reconstruct byte for byte. A new complete
source-only Donate build matches the previous ModKit RPK byte for byte. The
historical independent reader also confirms the original reference's resource
and script equivalence, including 17 scripts, 8,266 nodes and 41 model cases.
The SDK tests use synthetic references and data; no game assets are distributed.
These are offline checks, not a new engine test.

Nonempty localized text and notification formatter contexts remain separate
metadata. Removing these nine static blobs does not imply that all native
localization structures have been semantically decoded.
