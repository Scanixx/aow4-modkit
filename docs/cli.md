# CLI reference

Run `python -m aow4modkit --help`. An installed console entry point named
`aow4modkit` provides the same commands.

| Command | Effect |
|---|---|
| `init DIRECTORY` | Create a source example with a new UUID in an empty directory |
| `validate SOURCE.py` | Execute trusted source and validate/compile in memory |
| `build SOURCE.py` | Write mod directory and reports, without ZIP |
| `package SOURCE.py` | Write mod directory, reports, ZIP and SHA-256 sidecar |
| `inspect FILE.rpk` | Print resource metadata, IDs, URLs and dependencies |
| `inspect FILE.acp` | Print project metadata summary |
| `functions` | Print Markdown reference from the current function registry |
| `profiles` | List explicitly registered game format profiles |
| `snapshot FILES --output FILE.json` | Hash files and collect recognized structural inventories |
| `compare-snapshots BEFORE.json AFTER.json` | Report changes for manual review |
| `--version` | Print the SDK version, independent of any mod version |

`validate/build/package` accept `--game-version 2.3.0` and optional `--game-dir`.
`build/package` accept `--output DIRECTORY`; otherwise output is in `artifacts`
beside the source file. Compatibility warnings do not stop the build.
`--profile` explicitly selects a registered profile for validation/build/inspect.
See [editor update review](editor-updates.md) for snapshot options and limits.

Exit 0 means the requested offline operation completed, not that the mod was
engine-tested. Validation/format/I/O errors return 2 and print `error: ...`.
Syntax/runtime errors in a user's own Python source can still show a Python
traceback; use it to fix the source location.

Existing artifact directories are overwritten only when their ModKit manifest
matches the project and contains no stale/unowned files. Choose a fresh output
directory when changing the output file set. No automatic recursive deletion
is performed. ZIPs are assembled from planned files, not by zipping arbitrary
extra files found in a directory.

There are no install, editor-control, Workshop-upload or GitHub-publish commands.
