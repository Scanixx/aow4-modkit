# AoW4 ModKit

Experimental Python authoring tools for **Age of Wonders 4 2.3.x**.

Write named Python definitions, validate them, and build a mod folder and ZIP
containing native ACP/RPK data. Python runs during the build, **not in the game**.
This is an unofficial, limited toolkit, not a replacement for all editor features.

The first example builds without an installed game or any DLC. DLC definitions
are separate JSON files; only references actually used by a project contribute
requirements. Missing DLC files produce compatibility warnings, not build errors.

## Start here

Requires Python 3.11 or newer. Runtime dependencies: standard library only.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m aow4modkit validate examples/hello_realm/mod.py
.\.venv\Scripts\python.exe -m aow4modkit package examples/hello_realm/mod.py
```

To run from a source checkout without installing the package or downloading build
tools, set `PYTHONPATH` to its `src` directory instead:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m aow4modkit package examples/hello_realm/mod.py
```

This creates `examples/hello_realm/artifacts/HelloRealm-0.1.zip`. It does not
install, launch the game, control the editor, upload, or publish anything.

```python
from aow4modkit import ModProject, Trigger, actions, core, events

project = ModProject(
    name="Hello Realm", folder="HelloRealm", version="0.1", author="Your name",
    mod_id="9c98dd17-82c0-4a15-ad9c-eae6682eed58",
)
project.add_trigger(Trigger(
    key="hello_realm.first_turn",
    events=[events.new_turn()],
    conditions=[core.current_round().equals(1)],
    actions=[actions.log("[AoW4ModKit] Hello Realm loaded.")],
    once=True,
))
```

The UUID above belongs to the example. Use `init` for a new project with its own
UUID. Keep that UUID and resource keys stable for later updates.

## Documentation

- [A-to-Z quickstart](docs/quickstart.md)
- [Complete first example](examples/hello_realm/README.md)
- [Authoring API and common mistakes](docs/api.md)
- [Ascension resource recipes and existing-mod migration](docs/ascension-recipes.md)
- [Strategic spells, dialogs and asset packaging](docs/strategic-recipes.md)
- [Supported function signatures](docs/functions.md)
- [Adding DLC and content definitions](docs/content-packs.md)
- [2.3.x compatibility and verification limits](docs/compatibility.md)
- [Architecture and named constants](docs/architecture.md)
- [Reviewing game/editor updates](docs/editor-updates.md)
- [CLI reference](docs/cli.md)
- [Developer checks and future work](docs/development.md)

## Current scope

Supports observed ACP/RPK container layouts, global trigger resources, a typed
trigger-function registry, player loops and persistent variables, named recipes
for ascension traits, normal hero skills, hidden markers and tag books, singular
English MO messages, metadata, optional PNG thumbnails and deterministic ZIPs.
The strategic subset adds army spells, research/unlocks, embedded event dialogs
and unchanged asset packaging. It does not generate texture atlases.

Does not provide constructors for every hero-skill subtype, spell, unit, UI,
atlas, or arbitrary resource class. Inspection preserves unknown field bytes
where the enclosing layout is supported; it does not decompile complete mods.
Malformed and unsupported layouts fail rather than being guessed.

**Targeting 2.3.x is not a claim of end-to-end testing on every patch or DLC.**
The standalone example needs an in-game smoke test. Offline tests do not prove
Pantheon behavior, UI, save compatibility or network multiplayer.

No game binaries, game artwork or other authors' mod packages are included.
The authored code and documentation use the [MIT License](LICENSE).
See [provenance and distribution status](NOTICE.md). This preview has not yet
been published.
