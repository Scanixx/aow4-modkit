# Ascension-resource Python export

Included in the prepared **0.1.0a4** preview. Earlier development version notes
below record when individual features were added. See [release notes](releases/0.1.0a4.md).

This workflow helps you migrate your own existing mod into editable Python
and continue its development with ModKit. For another author's project, work
with their permission and retain its credits and license notices.

Local development support added in 0.1.0a4.dev5. The complete-RPK inverse
exporter now understands the existing public `TagBook`, `HiddenArtifactMarker`,
`AscensionTrait` and `HeroSkill` recipes, alongside side-property markers and
global triggers. This extends the same `export-python --scope pack` workflow.

```powershell
python -m aow4modkit export-python Example.rpk --scope pack --mod-id ORIGINAL-UUID --output artifacts/example-source
python -m aow4modkit build-pack artifacts/example-source --output artifacts/example-built/Example.rpk --reference Example.rpk
```

The original mod UUID is supplied explicitly. The source directory contains
no input RPK or binary template. `resources.py` constructs a `ResourcePackProject`;
`resources/*.py` calls the named public recipes. `resource_texts.py` contains
typed localization contexts, and `scripts/*.py` contains the executable graphs
as public API expressions. UUIDs, tag names, GUIDs, tag paths and owned book
references appear as readable Python values.

## Supported structure

- Tag books with one root and ordered, flat child tags. Original root, parent,
  sibling and child pointers are validated against the representable topology.
- Inert hidden eligibility markers with their original text contexts and tag
  sets, matching the public `HiddenArtifactMarker` defaults.
- Ascension traits with one supported owned-tag availability filter, an icon
  and an ordered list of hero-skill references.
- Hero skills with named title/description/icon/AI-priority/group references,
  ordered side-property grants and the selected profile's fixed defaults.

Tag sets and filters must refer to a matching tag book inside the same pack.
The referenced path and GUID must identify one of its declared tags. Books can
appear after their consumers in record order; the inverse decoder resolves
books before decoding those consumers. External or more complex tag books are
not assigned fabricated owned references.

For each inverse recipe, the decoder recompiles a candidate using the public
constructor and compares every resource payload field. Named values are
normalized structurally; unexposed defaults remain exact. Unsupported extra
fields/classes, altered defaults, missing mandatory fields, different filter
modes or nonrepresentable tag topology cause an explicit failure. No complete
record or unknown default is hidden in a preserved byte blob.

These are inverse adapters for the stated public recipes, not a universal
artifact or hero-skill decompiler. Supporting a different resource layout may
require a separate typed recipe rather than relaxing validation.

## Verification

The local More Secret Ascension Skills 0.4 export constructs all 11 records and
two global scripts (317 nodes) without a template. The new RPK is byte-identical
to its previous SDK migration and semantically equal to the retained original.
The independent historical reader confirms all resources; nine victory and
16 AI-startup model scenarios pass. This includes founding-race eligibility,
inherited AI transformations and their original startup/idempotence guards.

SDK tests use synthetic tags, UUIDs and resources. No game/mod assets or full
MSAS payload are included in SDK distributions. An extracted-wheel build needs
only generated Python and the SDK; game files, legacy tools and an installed
SDK are unnecessary. This does not imply a new game/Pantheon/multiplayer test.

MO translations and thumbnail/image assets are external to this RPK-only
workflow. Pack dependencies are retained explicitly. The exporter does not
infer DLC ownership or origin packs from serialized IDs; runtime content
requirements remain those of the original mod.
