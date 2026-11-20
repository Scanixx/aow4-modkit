# Template-free Python export of a complete RPK

Included in the prepared **0.1.0a4** preview. Earlier development version notes
below record when individual features were added. See [release notes](releases/0.1.0a4.md).

This workflow helps you migrate your own existing mod into editable Python
and continue its development with ModKit. For another author's project, work
with their permission and retain its credits and license notices.

Local development feature in **0.1.0a4.dev5**. Nothing in this development
revision is published. The current public release remains 0.1.0a3.

## Workflow

From the SDK source root:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m aow4modkit export-python Example.rpk --scope pack --mod-id ORIGINAL-UUID --output artifacts/example-source
python -m aow4modkit build-pack artifacts/example-source --output artifacts/example-built/Example.rpk
```

The original mod UUID must be supplied explicitly. Building executes trusted
generated Python; exporting only parses/generates source, never executes it.
No installation, editor, game executable or internet access is required.

Unlike trigger-only export, the output contains **no input.rpk or binary
template**. `resources.py` creates a public `ResourcePackProject` from Python
definitions. Every record, including its script fields, is constructed anew.

Optional verification after construction:

```powershell
python -m aow4modkit build-pack artifacts/example-source --output artifacts/example-built/Example.rpk --reference Example.rpk
```

`--reference` is read only after construction and is used solely for comparison.
Without a reference the report says `equivalent: null`, not that equivalence
was proven. With a reference, a mismatch blocks output unless intentional edits
are explicitly permitted through `--allow-changes`.

## Source layout

- `resources.py`: assembly entry point, returning `ResourcePackProject`.
- `resources/*.py`: named resource constructors and parameters, one file per record.
- `scripts/*.py`, `triggers.py`: the existing public-API trigger source.
- `pack-context.json`: explicit pack name, UUID, profile and dependency order.
- `resource_texts.py`, `localized_texts.py`: public API text definitions with typed contexts.
- `resource-texts.json`, `localized-links.json`: readable snapshots of those text definitions.
- `resource-links.json`: explicit script resource links.
- Named static-value constructors in `resources/*.py`; no static hex sidecar is needed for Donate.
- `preserved-parameters.json` is emitted only if legacy opaque values remain.
- `build.py`, `README.md`, `pack-export-manifest.json`: usage, context and hashes.

Resource parameters use `LocalizedText`, `ResourceLink`, `ResourceHandle` and
`DialogChoice`, with separate public `Script` definitions for initialization,
choice actions and visibility. Resource IDs/names, native URLs, array order,
choice IDs/modes and dependency order are retained. Locale keys and formatter
contexts do not supply the corresponding MO translations.

## Public RPK construction API

```python
from aow4modkit import ResourcePackProject, SideProperty

project = ResourcePackProject(
    name="EXAMPLE.RPK",
    mod_id="9c98dd17-82c0-4a15-ad9c-eae6682eed58",  # example UUID only
    dependencies=(),
    definitions=(SideProperty(key="marker", name="Example marker", resource_id=42),),
)
raw = project.build()
```

`ResourcePackProject` constructs the RPK container from the selected SDK profile.
It accepts pinned global `Trigger` objects and public resource recipes in explicit
record order. It has no input/template parameter. The returned bytes can be
written to a chosen workspace path. `compile()` returns a `ResourcePack` object.

This API has explicit native context rather than automatic dependency inference:
serialized links are allowed without fabricated origin metadata. New
`ResourceHandle(id, name)` represents a lightweight reference that contains no
URL. `ResourceLink` retains a full native link. A launcher-level `ModProject`
still requires declared `ResourceRef`/owned references for dependency inference.

This is RPK construction, not generation of a complete launcher mod, MO catalog,
CLB atlas or image files. Those external dependencies are referenced as before.

## Supported inverse resource recipes

The initial strict scope supports the observed 2.3 profile's canonical one-store,
one-group layout, with known default pack/store/record metadata, and:

- Generic empty `SideProperty` markers.
- Flat owned `TagBook`, `HiddenArtifactMarker`, `AscensionTrait` and profile-default `HeroSkill` recipes.
- Global `Trigger` resources.
- `StrategicArmySpell`, `ArmyTargeter`, `StoryEvent` and `DialogChoice`.
- `ResearchSkill`, `SpellUnlockProperty` and `TextureAtlasIcon`.

These are inverse adapters to existing named SDK recipes, not a universal
resource decompiler. Extra fields/classes, unsupported metadata, missing names,
unrepresentable indices or incompatible choice allocator state fail export.
They are not silently discarded or copied as whole-resource binary blobs.
Packs with supported resources and no scripts are also accepted.

## Typed static values

The nine static fields previously retained as 761 bytes now use public Python
constructors. See [Native static values](native-static-values.md) for every
field, its wire structure, examples and interpretation limits. All nine can be
encoded byte for byte without a saved field payload.

The inverse exporter rejects extra fields and unsupported native structures.
`PreservedParameter` remains supported when compiling older authored recipes,
so existing mod payloads remain unchanged. The supported inverse recipes now
expect the named native layouts rather than accepting arbitrary static blobs.
Nonempty localized formatter contexts now use [typed text contexts](text-contexts.md);
this change does not claim to decode every localization or game resource type.

## Comparison and validation

`compare_resource_packs(before, after)` decodes all supported recipe fields and
registered scripts, checks pack/store/record metadata and original dependency
order, and compares their normalized values. Named static values and all scalar/reference values are compared.
It ignores only approved table framing, generated node identity bytes (parent
resource IDs are checked), and the resulting RPK payload length.

`build_pack_export(directory, output, reference=..., allow_changes=False)` is the
public convenience API behind CLI and the generated build.py. It explicitly
loads trusted Python and protects unowned or modified output files.

The Donate export was independently compared using the historical reader:
nine resources, 17 scripts and 8,266 nodes match; all 41 behavior-model scenarios
pass. The newly constructed RPK also matches the existing ModKit migration's
RPK byte for byte. Its checksum differs from the older reference RPK because
known framing and generated identities changed. No new engine test is implied.

Synthetic tests additionally block **all RPK file reads during construction**,
exercise nonsequential choice IDs, explicit dependency order, missing context,
unknown/extra fields, typed static data, legacy authoring compatibility, optional reference checks and output
ownership. The SDK distribution uses synthetic fixtures, not full game/mod data.

See [Ascension-resource export](ascension-python-export.md) for the strict additional
scope and offline MSAS verification.
