# Developer workflow

## Local checks

After installing the source package:

```powershell
python -m unittest discover -s tests -v
python -m aow4modkit validate examples/hello_realm/mod.py
python -m aow4modkit package examples/hello_realm/mod.py
```

Tests require no game, DLC, Capstone, Pillow or other mod. They exercise malformed
binary data, unknown-field preservation, type errors, native function emission,
stable IDs, optional/new DLC definitions, compatibility warnings, localization,
metadata tags, ZIP hashes, reproducibility and output ownership.

The workspace preview was checked with Python 3.12. Python 3.11+ is the declared
minimum; a multi-version CI matrix remains a public-release task.

Generate/check reference docs from the registry with:

```powershell
python tools/generate_reference.py
```

## Extending a known function

1. Establish its exact type group, ID, parameters and applicable context.
2. Name its constant in the relevant enum.
3. Add a `FunctionSpec` with descriptions and parameter types.
4. Add a readable wrapper, retaining native side-effect distinctions.
5. Test rejected types and the emitted native structure, not just wrapper output.
6. Regenerate function documentation and record evidence/runtime limits.

External DLC refs are independent JSON data; use the [content guide](content-packs.md).
New binary classes require a schema and serializer, not only a new numeric ID.

## Before a GitHub release

- Retain the MIT license and copyright notice in source and wheel distributions.
- Perform a real 2.3.x game smoke test of the standalone Hello Realm constructor.
- Confirm supported patches and keep compatibility claims scoped to evidence.
- Review source/package contents for game binaries, artwork and local paths.
- Test wheel/source installation and the documented commands in a clean folder.
- Add a Python version/platform CI matrix before broad compatibility claims.

## Planned authoring migrations

More Secret Ascension Skills 0.4 now has public-API authoring under its
`source/` directory, independently compared to the unchanged original release.
Donate Spell migration remains a follow-up. Keep historical ZIPs unchanged and
compare resource meaning/behavior before switching released builds; changed
binary field ordering alone is not necessarily a gameplay change.

The current task prepares local code and artifacts. It does not publish the
repository or authorize an upload of game data.
