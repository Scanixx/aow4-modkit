# Hello Realm: first complete example

This tiny mod demonstrates the path from a readable Python file to ACP/RPK/ZIP.
It declares no DLC and builds without game files. Target: AoW4 **2.3.x**.

## Source, step by step

1. `ModProject(...)` declares identity, version, author, metadata and optional text.
2. The UUID belongs to this supplied example; `init` generates a new one for your
   own project. Do not reuse the example's UUID for a different mod.
3. `Trigger(key=...)` gives the trigger a stable symbolic key.
4. `events.new_turn()` creates a native event node.
5. `core.current_round().equals(1)` creates a native integer comparison.
6. `actions.log(...)` creates a native diagnostic action.
7. `once=True` uses the engine's global trigger deactivation flag.
8. `package` serializes these definitions and constructs all file wrappers.

The source is not copied into the installable mod folder. The game does not need
Python, ModKit, another mod, or a game executable supplied by this repository.

## Commands from the repository root

```powershell
python -m aow4modkit validate examples/hello_realm/mod.py
python -m aow4modkit package examples/hello_realm/mod.py
python -m aow4modkit inspect examples/hello_realm/artifacts/HelloRealm-0.1/HelloRealm/Packs/hellorealm.rpk
```

The default artifact ZIP is `examples/hello_realm/artifacts/HelloRealm-0.1.zip`.
Use `--output artifacts` to choose a different artifact root.

## Expected files

```text
HelloRealm-0.1/
  HelloRealm/
    HelloRealm.acp
    .metadata/metadata.json
    Packs/hellorealm.rpk
  manifest.json
  BUILD-REPORT.json
  COMPATIBILITY.json
  COMPATIBILITY.txt
  README.txt
  CHANGELOG.txt
  WORKSHOP-DESCRIPTION.txt
```

There is no thumbnail or MO file because this example does not need one. Do not
mistake the native log string for a localized UI resource.

## Manual test and cleanup

Follow [quickstart steps 8-9](../../docs/quickstart.md). Load a new realm with the
example enabled and check configured native diagnostics for:

```text
[AoW4ModKit] Hello Realm: first-turn trigger executed.
```

It should be written once when the first-turn event satisfies the round-1
condition. It is not an on-screen dialog. Runtime logging and engine load are
not yet confirmed for this standalone example. Record the actual 2.3.x patch
and your result before calling it tested.

The example deliberately avoids DLC, research, race modifications and save
references to custom skills. It teaches packaging before adding gameplay logic.
