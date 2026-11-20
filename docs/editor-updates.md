# Reviewing official game and editor updates

ModKit's initial named profile is `aow4-2.3-observed-v1`. It explicitly describes
the observed 2.3.x-target framing and function registry. DLC catalogs describe
content; **a new DLC catalog and a new engine format profile are different things**.

## Establish a baseline

Keep a small reference project created/saved by the official editor and its RPK.
Record the actual game/editor version. Choose representative files whose changes
you can explain. An editor executable can be included as a hash-only reference;
ModKit does not run, inject into or disassemble it.

```powershell
python -m aow4modkit profiles
python -m aow4modkit snapshot reference.acp reference.rpk --output before.json --game-version 2.3.0
```

`--editor-version` is an optional author-supplied label. Inputs are read only.
The snapshot records hashes and recognized field inventories, not resource
payloads. It is not a replacement for a backup of your source project.

## After an update

Save a copy of the same reference project using the updated official editor.
Capture the same named files and compare:

```powershell
python -m aow4modkit snapshot reference.acp reference.rpk --output after.json --game-version 2.3.1
python -m aow4modkit compare-snapshots before.json after.json
```

`content_hash_only` means recognized structure inventories stayed the same, not
that behavior is proven unchanged. `structural_review` means field inventories,
headers or supported parsing changed. Different content/optional fields can also
cause structural differences; a report cannot infer an ABI break from that alone.

## Adapting ModKit

1. Review official release notes and your reference-file differences.
2. Separate new content IDs from changed serializers or trigger signatures.
3. For known classes, add DLC content data independently.
4. If wire framing changed, add an explicitly named `GameProfile` in a separate
   versioned definition and register it. Preserve the older profile.
5. If field tables/classes changed fundamentally, implement a format/schema
   adapter with fixtures; changing a header constant alone is insufficient.
6. Update named fields/functions and their documentation based on evidence.
7. Run old-profile regressions and new-profile tests, then editor/game smoke tests.
8. Record the exact tested patches and emit compatibility/release notes.

`ModProject(profile=...)` selects the constructor and compiler profile.
CLI `--profile` can select a registered profile explicitly. A compiler rejects
functions absent from the selected profile. Public wrappers retain the initial
signature subset; changing signatures requires updating wrappers and tests too.

No periodic web monitoring is configured. This is a repeatable local review
workflow, ready to run when the official game/editor changes. Unknown versions
are never silently accepted as supported.
