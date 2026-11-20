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
Donate Spell 0.14 also uses the public API and retains its reference archive. Keep historical ZIPs unchanged and
compare resource meaning/behavior before switching released builds; changed
binary field ordering alone is not necessarily a gameplay change.

Build and inspection commands create local artifacts. They do not publish a
repository or upload game data.

## Integrated trigger decoder

Local 0.1.0a4.dev0 includes `aow4modkit.analysis` and CLI trigger decoding.
See [the implementation guide](trigger-analysis.md) and [longer export design](reverse-export-design.md).

Local 0.1.0a4.dev1 adds [strict trigger Python export and explicit rebuild](trigger-python-export.md).
The public 0.1.0a3 binaries remain unchanged.

Local 0.1.0a4.dev2 adds [complete RPK Python export](full-rpk-python-export.md)
for the explicitly supported resource subset, without an input binary template.
