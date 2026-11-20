# DLC definitions and content extensions

DLC catalogs are **data**, separate from binary serialization and trigger code.
The first supplied catalogs are deliberately small:

- `src/aow4modkit/content_definitions/rise_from_ruin.json`
- `src/aow4modkit/content_definitions/silver_seas.json`

They contain named references used during development, not a complete DLC dump.
They can be loaded without installing the game or owning either DLC.

```python
from aow4modkit import ContentCatalog

catalog = ContentCatalog().load_builtin("rise_from_ruin")
fractured = catalog.ref("rise_from_ruin.fractured_transformation")
```

Using `fractured` in a trigger adds its native pack dependency and its DLC
requirement. Loading this catalog without using any reference adds neither.
Native resource payloads are resolved by the game when the mod runs, not copied
into a build from a catalog.

## A self-contained new DLC definition

Create your own JSON file; editing ModKit source is not necessary:

```json
{
  "format_version": 1,
  "dlc": {
    "key": "your_dlc",
    "title": "Your DLC title",
    "content_folder": "YourDlcContentFolder",
    "minimum_game_version": "2.3.1"
  },
  "resources": [
    {
      "key": "your_dlc.example_property",
      "kind": "side_property",
      "id": "ABCD000000000001",
      "name": "Example property",
      "url": "[#ABCD000000000001]0\\0",
      "pack": "YourDlcProperties.rpk"
    }
  ]
}
```

The ID, name, URL and pack above are **illustrative placeholders**, not game
content. Read the actual metadata from the appropriate pack with `inspect`.
Preserve the URL exactly, including any native repeated separators. JSON escapes
each backslash with another backslash; do not confuse this with Python source.

Load it from a source-relative path:

```python
from pathlib import Path
from aow4modkit import ContentCatalog

catalog = ContentCatalog().load(
    Path(__file__).resolve().parent / "content" / "your_dlc.json"
)
property_ref = catalog.ref("your_dlc.example_property")
```

`dlc` can be `null` for base-game content. `minimum_game_version` is optional;
omit it when the exact minimum patch is not established. A newer minimum emits
warnings against the toolkit's 2.3 baseline and an older supplied game version.

Known reference kinds are `racial_transformation`, `hero_skill`, `side_property`,
`token`, `icon`, `ai_priority`, `hero_skill_group`, and `other`. Relevant API calls reject a known mismatched kind. `other`
allows an explicitly unclassified reference, with a compatibility warning; it
does not prove the resource is usable by that engine operation.

Catalog merging rejects duplicate keys or resource IDs. Keep your keys stable.
New hero skills and properties already defined in a native pack or another mod
can be represented as refs. This does not create those resources or include their
payloads; the providing DLC/mod remains a runtime dependency.

## When a new schema is needed

A new DLC may reuse known classes, in which case references can be added without
core edits. If it introduces a new binary class or function signature, adding an
ID is insufficient. Implement a separately named schema/serializer and tests
before exposing it through high-level authoring. The public `HeroSkill` recipe now covers the observed normal hero-skill subtype;
this preview does not have an arbitrary class-plugin compiler or every skill subtype.

The low-level container can retain opaque fields of supported enclosing layouts.
That is preservation, not semantic knowledge or permission to invent class data.

## Compatibility reports for players

Every build writes `COMPATIBILITY.json` and `COMPATIBILITY.txt`, including:

- baseline target `2.3.*` and optional supplied actual version;
- only DLC required by used references or explicit project declarations;
- missing/unverified content files and unknown resource-kind warnings;
- project-authored compatibility notes;
- suggested description text.

Copy and edit the generated requirement text for a mod description. Add a
changelog entry if an update introduces a new required DLC. Reports do not claim
that files present on disk are licensed or that the game successfully loaded
the resource. Multiplayer, saves and balance still require real testing.
