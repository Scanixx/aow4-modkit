# Compatibility and evidence

## Game baseline

**AoW4 ModKit starts at the Age of Wonders 4 2.3.x baseline.** `2.3.*` is the
target range in reports, not a magic wildcard written into every launcher field.
Later minor versions may keep compatible formats, but need fresh verification.
They emit `OUTSIDE_TARGET_SERIES` when supplied, rather than silently claiming
support. Unsupported binary signatures always fail.

`--game-version` is an author-supplied actual version, not an ownership/version
detector. Omitting it emits a warning. It is not inferred from Windows time,
Steam presence or a guessed executable filename.

## What is supported

- RPK signature `52504b001a000004`, observed 176-byte wrapper.
- Three explicitly listed content-store framing headers.
- CPR/TEUserContentProjectData ACP wrapper and field tables.
- Opaque preservation of unknown fields inside supported containers.
- One-store, one-group new packs with global trigger resources.
- Named observed recipes for ascension traits, normal hero skills, artifact/side
  markers and tag books; see ascension-recipes.md.
- The function subset documented in [functions.md](functions.md).
- Singular English MO catalogs; no plural/context authoring API yet.
- Native project metadata and optional existing PNG thumbnails.

The wire layouts and function IDs originate in local data inspection. Related
gameplay paths were used by Donate Spell and More Secret Ascension Skills. User
tests of those mods are evidence for their specific paths, not proof for every
ModKit function or for the new standalone constructor on every 2.3 patch.

The new SDK has offline tests. Its example needs a manual engine smoke test.
No runtime validation is claimed for this workspace preview. No executable
hashes or disassembly tools are required for ordinary builds.

## DLC separation

The toolkit and first example require no DLC. Used refs contribute declared DLC
and RPK dependencies; unused loaded catalogs do not. Missing DLC files are
warnings because a modder may build for a game installation on another machine.

Optional `--game-dir` performs read-only existence checks. It does not inspect
Steam licenses. The current external check locates the pack file, not the
resource record within it; IDs/URLs are author-declared metadata. Treat that
boundary honestly when preparing a description.

## Verification levels

1. **Container checks:** byte framing, bounds, supported headers, field retention.
2. **Authoring checks:** expression types, parameters, resource IDs, catalog kinds.
3. **Package checks:** manifests, hashes, ZIP CRC, reproducible contents.
4. **File availability:** optional local DLC/pack existence checks.
5. **Engine behavior:** requires manual game tests; not performed by ModKit.

Passing one level does not imply passing the next. An offline model cannot prove
engine callbacks, UI, placement, save/Pantheon persistence or synchronization.

## Core warnings

| Code | Meaning |
|---|---|
| `GAME_VERSION_NOT_CHECKED` | No actual game version was supplied |
| `OUTSIDE_TARGET_SERIES` | Supplied version is outside 2.3.x |
| `DLC_NOT_CHECKED` | Required DLC files were not examined |
| `DLC_FILES_MISSING` | Declared DLC content folder was not found |
| `EXTERNAL_PACK_MISSING` | Referenced RPK filename was not found |
| `DLC_NEWER_THAN_TARGET` | Declared minimum exceeds base 2.3.0; review exact patch requirement |
| `GAME_TOO_OLD_FOR_DLC` | Supplied game version is below that DLC definition's minimum |
| `REFERENCE_KIND_UNVERIFIED` | A ref has no known semantic kind |
| `DEPENDENCY_MANIFEST_PRESERVED` | An audited existing dependency list/order overrides inferred pack origins; inspect the report |

Validation errors, such as passing an integer as a player, stop the build.
Compatibility warnings are reported without blocking serialization.
