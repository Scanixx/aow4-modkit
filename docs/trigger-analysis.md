# Readable RPK trigger analysis

Introduced in 0.1.0a4.dev0 and available in the local **0.1.0a4.dev1** development tree. This feature is not
in the published 0.1.0a3 wheel. It uses only the SDK and Python standard library.
No installed game, editor, EXE analysis image or historical tools are required.

## CLI

From a source checkout, without installing anything:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m aow4modkit inspect path/to/Example.rpk --detail
python -m aow4modkit decode path/to/Example.rpk --output artifacts/example-analysis
```

The existing `inspect` command without `--detail` still produces the original
metadata-only output. `decode` produces:

| File | Content |
|---|---|
| `report.md` | Scope, script index, function usage and diagnostics |
| `triggers.txt` | All scripts as one readable outline |
| `scripts/001-RESOURCEID.txt` etc. | Individual global/embedded scripts |
| `decoded.json` | Versioned, flat node graph with exact source ranges |
| `input.rpk` | Unchanged original bytes, including unknown values |
| `analysis-manifest.json` | Output ownership and file hashes |

Output directories must be empty or belong to the same input and this analysis
tool. Modified reports and unrelated files are protected: choose a new output
directory instead of overwriting them. CLI input files cannot be inside the
analysis output directory. No input is changed or executed.

Exit code 0 means the report was produced without semantic errors; warnings may
still exist. Exit code 3 means the report was produced with semantic errors,
such as invalid argument slots or booleans. Exit code 2 indicates a fatal
format, limit, filesystem or output-ownership failure. Unknown functions and
fields are explicit diagnostics; success never means full mod understanding.

## Python API

```python
from aow4modkit.analysis import read_pack, render_script, write_analysis

decoded = read_pack("Example.rpk")
print(decoded.statistics)
for script in decoded.scripts:
    print(render_script(script))
write_analysis(decoded, "artifacts/example-analysis")
```

`decode_pack(data: bytes, source_name=..., profile=..., limits=...)` handles an
in-memory pack. `read_pack` performs a bounded read. `DecodeLimits` configures
input size, cumulative parsed bytes, node/field/resource counts, depth and
diagnostics. Defaults include 64 MiB input, 512 MiB cumulative parsed bytes,
200,000 nodes and depth 128. Cumulative parsed bytes include nested re-reads,
so they can substantially exceed the input size. This is not a memory-use cap.

All source ranges are `(start, end)` byte offsets in the **original RPK**, with
end exclusive. Use `decoded.source_bytes(origin.span)` to recover a value and
check its recorded SHA-256. Resource/class fields not semantically interpreted
remain recoverable through their ranges and the original input copy.

## What is decoded

- Global trigger resources, class `0x474247`.
- Story-event initialization in base class `0x4774F0`, field 1.
- Story-event choices in class `0x474393`, field 4, including their action and
  visibility scripts, explicit list IDs, category, text key and visibility mode.
- All four script phases: events, conditions, actions and setups.
- Context, once/enabled/active state, comments, child order and argument slots.
- Supported function signatures, presets, internal/external links and localized
  notification keys with original formatter bytes.

Other resource classes are inventoried only. The report states this separately
from script coverage. There is no heuristic scan of arbitrary fields for bytes
that happen to resemble a script. New script containers require a verified
locator. Binary corruption fails; unsupported semantic values remain explicit.

The readable outline is **not executable Python**. CHECK/THEN/OTHERWISE labels
expose registered `actions.when` branches without rewriting their evaluation
semantics as Python `if`. Literal wrappers are compacted for display only; the
IR retains every original node. Disabled states are shown, not simulated.

The decoder does not produce a buildable `mod.py`, translate missing MO strings,
infer DLC origin from an ID, compile CLB files or certify gameplay behavior.
The [strict trigger Python exporter](trigger-python-export.md) now consumes this IR.

## Native details established by this implementation

1. The compiler's integer, boolean and string literals contain getter calls
   `10:0`, `12:0`, `19:0` around presets of types 9, 11 and 18. The analysis
   signature table names these `literal.integer/boolean/string`. They are
   decoder intrinsics, not new public `invoke()` functions.
2. `comparisons.integer` and `conditions.integer_equals` share native `1:2`.
   Reverse decoding deterministically selects `comparisons.integer` and retains
   the alias. It does not replace greater-than with equality.
3. Setup nodes keep native type 2, rather than action type 3. Only the verified
   setup counterparts already supported by the compiler are resolved by name.
4. Script settings use field 0 for native context; 2 for once; 3/4 for enabled
   and active; 5 for the existing comment; and 11/12/13/14 for the four phases.
5. A node's serialized identity is not a safe deduplication key. The original
   Donate 0.14 input contains 428 repeated identities; the migrated input has
   none. Both contain the same 8,266-node executable structure. This observation
   alone does not establish an engine bug or prove any cache behavior.
6. Native story choice IDs and visibility mode belong to the choice wrapper,
   not to the contained script. They remain distinct from array position.

`FieldTable.field_spans` is a new reusable format-reader facility. It stores
read-time ranges relative to the buffer supplied to `FieldTable.read`, including
its offset. The analysis decoder adds enclosing offsets to obtain absolute RPK
ranges. Editing table fields does not update those original ranges; serialization
and dataclass equality are unchanged by this provenance metadata.

## IR and unsupported data

The JSON uses `ir_version: 1` and `node_representation: flat-v1`. Script phases
refer to stable export-local node IDs; each node lists its children by ID.
This avoids huge nested JSON indentation for deeply guarded graphs. The
in-memory API retains a tree for convenient traversal with `walk_nodes`.

Unknown call signatures retain their original function ID, child order and
slots. Unknown node classes remain opaque; their inheritance and field 2/7
layouts are not guessed. Extra fields in known nodes retain source references
and diagnostics. The complete original file accompanies exported analysis, so
no unknown data has to be silently converted into made-up Python behavior.

Reports can contain an input author's text and data. They are working outputs,
not SDK distribution content. Their presence does not grant rights to republish
the input. This tool does not download, upload or publish mods automatically.

## Offline verification

Synthetic tests cover literal wrappers, named signatures/aliases, embedded
dialog scripts, nonsequential choice IDs, setup types, disabled states, extra
fields, unknown nodes/functions, malformed arguments/framing, limits, CLI
compatibility, exact source ranges and output ownership.

Our separate development audit compared both Donate 0.14 RPKs against the
historical independent reader: 17 scripts, 8,266 nodes and 51,478 node-field
ranges per input. All 41 existing model cases pass using the newly decoded
graphs. Those historical tools are not runtime dependencies or SDK fixtures.
No game/editor execution or new save/multiplayer validation is implied.
