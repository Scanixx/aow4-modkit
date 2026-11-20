# Rebuildable Python export of triggers

Included in the prepared **0.1.0a4** preview. Earlier development version notes
below record when individual features were added. See [release notes](releases/0.1.0a4.md).

This workflow helps you migrate your own existing mod into editable Python
and continue its development with ModKit. For another author's project, work
with their permission and retain its credits and license notices.

Local development feature in **0.1.0a4.dev1**, not yet published. It exports
registered trigger scripts, not an entire mod's resources as Python.

## Export and rebuild

From the SDK source root, without installing anything:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m aow4modkit export-python Example.rpk --output artifacts/example-python --mod-id ORIGINAL-PROJECT-UUID
python -m aow4modkit rebuild-triggers artifacts/example-python --output artifacts/example-rebuilt/Example.rpk
```

Substitute the actual project UUID. The `--mod-id` option can be omitted at
export, but must then be supplied at rebuild. An RPK does not establish that
UUID, so the tool never derives or invents one. No editor or game files beyond
the selected input are needed.

You can also explicitly run `rebuild.py --output path/to/Example.rpk` from the
exported directory. Both rebuild commands execute trusted Python source, just
like the existing ModKit project builder. **Inspection and export never execute
the generated Python.** Export validates syntax using Python AST/compile only.

The export directory must be new or empty; existing source is never overwritten.
Rebuild output must be a separate RPK and is accompanied by an ownership and
verification JSON file. Existing unowned or manually changed outputs are protected.

## Files and readability

- `scripts/*.py`: one `build_script(references, texts)` function per global,
  initialization, choice-action or choice-visibility script.
- `triggers.py`: assembles those definitions, using only public ModKit types.
- `resource-links.json`: exact resource IDs, names and serialized URLs.
- `localized-links.json`: localized keys and their original formatter contexts.
- `script-bindings.json`: original resource, role, location and choice list ID.
- `input.rpk`: explicit template for everything outside the exported scripts.
- `rebuild.py`, `README.md` and `export-manifest.json`: entry point, usage and hashes.

Native branches become small, named Python helper functions. Repeated immutable
expressions use descriptive local variables rather than one huge numbered list
of temporary definitions. These variables represent future native reads: they
do not cache a live player, unit or variable value. Each occurrence still emits
fresh native nodes when compiled. Native guards, argument order, list kinds,
setup/action distinctions and actual comparison operators remain unchanged.

Names of helpers are generated hints based on known functions and variable
names. They are not recovered original source or an inference of gameplay intent.
Existing serialized script comments are preserved verbatim. Embedded scripts
use public `Script`; global scripts use public `Trigger` with pinned resource IDs.

Source text from an input, including names/comments/log messages, is emitted as
AST string constants. It is not interpolated as Python code. No serialized
executable graph is stored in either JSON file or loaded by `build_triggers()`.
That function can construct every definition even without `input.rpk` present.

## Why the original RPK template remains

The current inverse adapters cover scripts. Spell definitions, research,
targeters, dialog wrappers and other resource data remain in the original pack.
Rebuild compiles **every registered script** and replaces only its registered
field. Coverage must match exactly; a missing definition cannot silently fall
back to the original graph. A separate compiler allocator per containing
resource avoids node-identity collisions across embedded scripts.

Choice list IDs, visibility modes, categories, text/formatter data and their
resource ownership remain in the untouched wrappers. This is an explicit
trigger-only migration, not a claim that unknown resources were reconstructed.
Exporting those wrappers as `DialogChoice`/resource recipes is a later stage.

## Serialized links without guessed origins

`ResourceLink(resource_id, name, url)` is a new public value for an exact native
link. It does not invent a pack filename or DLC requirement. This is useful
when recompiling existing scripts whose external origins are unresolved.

`ResourceRef` retains its original constructor/signature and adds known origin
metadata through the same link base. A new full `ModProject` requires declared
`ResourceRef`/owned references; it rejects bare `ResourceLink` values. Complete
project dependency inference cannot be justified by merely seeing a numeric ID.

## Strict acceptance

The exporter rejects unknown functions/classes/fields, disabled/inactive states
the compiler cannot emit, unsupported contexts, noncanonical native slots or
array indices, unrepresentable standalone presets and unnamed comparisons.
Unsupported executable data is never hidden in `PreservedParameter` or replaced
by a placeholder. Use `decode` for readable analysis of unsupported inputs.

The default rebuild requires normalized equivalence. It compares every exported
script and all nonscript envelope values. `--allow-changes` explicitly permits
intentional edits and writes a report with `equivalent: false` when appropriate.
It does not change the input template or install the rebuilt RPK.

## Comparison guarantees and limits

`compare_trigger_packs(before, after)` independently decodes both binary packs
and compares native classes/types/functions, scalar values, argument slots and
order, list structure, script flags/context/comments, original parent resource
IDs, localized formatting and choice metadata. A separate envelope comparison
masks only registered script fields and checks every other field value.

Only known field-table directory framing, the corresponding RPK payload length
and generated node identity bytes are ignored. Identity parent resource IDs are
still checked. Inputs with unresolved diagnostics cannot be declared equivalent.
An unchanged opaque blob is preservation evidence, not semantic resource decoding.

This is scoped offline equivalence. It cannot certify native callbacks,
save/Pantheon persistence or multiplayer. Rebuilding does not recover an
author's original Python, missing comments or editor workflow.

## Public Python API

```python
from aow4modkit.analysis import (
    read_pack, export_trigger_python, rebuild_trigger_pack, compare_trigger_packs,
)

decoded = read_pack("Example.rpk")
export_trigger_python(decoded, "artifacts/source", mod_id=original_uuid)
# Explicitly load trusted generated source to get a path -> Trigger/Script map.
rebuilt = rebuild_trigger_pack(original_bytes, definitions, mod_id=original_uuid)
report = compare_trigger_packs(original_bytes, rebuilt)
```

`rebuild_export(directory, output, mod_id=..., allow_changes=False)` is the
explicit trusted-source loading convenience used by CLI/generated rebuild.py.
`ResourcePack.replace_record` is also public for replacing one existing record
while preserving other records and store metadata.

## Validation

Synthetic tests cover source escaping, no source execution during export,
template-independent definition construction, missing context/definitions,
strict failures, external link URLs, localized formatter bytes, setup scripts,
choice IDs, edited source detection, output ownership and deterministic rebuilds.

Donate validation additionally uses the retained independent binary reader and
existing behavior model, rather than relying only on the exporter and decoder
agreeing with one another. Exported Python and original mod data stay outside
the SDK's distributed fixtures. The public 0.1.0a3 assets remain unchanged.

## Complete RPK scope

Local 0.1.0a4.dev2 additionally supports [template-free export of supported complete RPKs](full-rpk-python-export.md).
The trigger-only mode described here still intentionally retains its nonscript template.

## Typed text export update

Local 0.1.0a4.dev4 writes notification keys and formatter metadata as public API
objects in localized_texts.py. localized-links.json is now a readable snapshot
without context_hex. See [Text contexts](text-contexts.md). Legacy authored byte
contexts still compile; unsupported inverse formatter structures fail explicitly.
