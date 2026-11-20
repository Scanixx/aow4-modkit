# From Python source to a testable mod ZIP

## 1. Prepare the tools

Use Python 3.11+ on a development machine. A game installation is not needed to
build the no-DLC example. The target game series is **AoW4 2.3.x**.

From the repository root, create a virtual environment and install the checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

The library has no third-party runtime dependencies. Installing from source may
need setuptools as a build dependency. With no network or package installation,
use `PYTHONPATH` as shown in the README. The following commands assume the package
is installed in the active Python environment; substitute the venv executable.

## 2. Build the supplied example first

```powershell
python -m aow4modkit validate examples/hello_realm/mod.py
python -m aow4modkit package examples/hello_realm/mod.py
```

No game version is silently detected. `GAME_VERSION_NOT_CHECKED` is expected.
If you have independently checked the actual installed version, supply it:

```powershell
python -m aow4modkit package examples/hello_realm/mod.py --game-version 2.3.0
```

`2.3.0` is an example input, not a statement about your installation. Do not use a
wildcard here. The documented target series itself is `2.3.*`.

## 3. Create your own source project

```powershell
python -m aow4modkit init my_first_mod
```

Edit `my_first_mod/mod.py`: change the displayed name, folder, author,
description, tags and trigger behavior. Init generates a fresh UUID. Keep it
stable across updates. Use stable trigger keys; they determine resource IDs.

The file defines a `ModProject` variable called `project`. Loading this source
executes Python during the build. It is your trusted development source, not a
safe import mechanism for unknown Python files. Inspecting an RPK does not load
or execute its contents as Python.

## 4. Understand the example

Its global trigger waits for `Time.NewTurn`, requires round 1, and sends a
diagnostic message to the native logging system. `once=True` deactivates that
global trigger after a successful firing. It is not a once-per-player counter.

There is no popup, reward, skill, spell or unit change. Python expressions such
as `.equals(1)` describe future engine operations; they are not evaluated while
building. See [the walkthrough](../examples/hello_realm/README.md).

## 5. Add references and declare compatibility

Load an optional [content catalog](content-packs.md) and use its named refs.
Only actually used references add pack/DLC requirements. Merely loading the
catalog does not require its DLC.

An optional `--game-dir "X:\Games\Age of Wonders 4"`
checks content-folder and pack-file availability by reading files. It does not
check Steam licenses or prove that a referenced resource has the expected engine
behavior. Missing files warn without blocking serialization.

## 6. Add text and an optional thumbnail

`project.messages` accepts singular English message keys and values. The MO
writer creates a localization file and pack dependency. Adding a key does not
automatically attach it to a resource field; this first high-level API does not
yet author every localized resource class.

For a prepared PNG:

```python
from pathlib import Path
project.thumbnail = Path(__file__).resolve().parent / "thumbnail.png"
```

The image is copied to the mod root and `.metadata`, and ACP receives the path.
It is not converted into an in-game atlas or CLB. Always resolve source assets
relative to `__file__`, not the process working directory.

## 7. Validate and package

```powershell
python -m aow4modkit validate my_first_mod/mod.py
python -m aow4modkit package my_first_mod/mod.py --output artifacts
```

The artifact folder contains the installable mod directory, `manifest.json`,
`BUILD-REPORT.json`, and human/JSON compatibility reports. Optional project
README, release notes and Workshop description are included beside the mod.
The ZIP contains this same layout. It contains no Python runtime code.

Review `COMPATIBILITY.txt` when writing your description and patch notes. Its
text is a declaration/check summary, not a certification of game compatibility.

## 8. Install and test manually

Close the game and launcher. Back up saves before tests. Copy **only the mod
folder**, not the report files, into your AoW4 user Mods directory, commonly:

```text
%USERPROFILE%\Documents\Paradox Interactive\Age of Wonders 4\Mods\
```

The Documents folder can be redirected; use your actual AoW4 user directory.
Enable the mod in a test playset and start a new realm on a 2.3.x game build.
To test Hello Realm, inspect the native diagnostic output for `[AoW4ModKit]`.
The logging capture must be enabled/configured for your setup. No visible
notification is expected. If diagnostic output is unavailable, do not treat
successful packaging alone as proof that the engine executed the trigger.

Record your actual game version, mod load result, first-turn message and whether
the message repeats. These are manual runtime checks, separate from SDK tests.

## 9. Remove the example

Close the game/launcher, disable the example in the playset, and remove only its
local mod folder. Use the pre-test save backup if needed. More complex mods may
store custom resource references in saves/Pantheon; do not assume their removal
is safe just because this minimal example is simple.

## 10. Prepare an update or publication

Keep `mod_id`, owned trigger keys and the existing Workshop item identity. Change
the mod version and release notes; rebuild and review requirements again.
`workshop_id` is recorded in the build report for author reference. This tool does
not implement an uploader or guarantee which metadata fields a launcher upload
dialog retains. Review the title, tags, DLC requirements and changelog there.

The toolkit itself and the example have not been published by these commands.
