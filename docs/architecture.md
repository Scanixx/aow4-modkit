# Architecture and constants

```text
Python source -> typed expressions -> trigger compiler -> ACP/RPK/MO files
                                       |                     |
Content JSON -> used refs/DLC ----------+-> compatibility -----+-> ZIP
```

The public package never imports the old workspace's `tools`, Donate Spell or
More Secret Ascension Skills. No old ZIP or installed mod is a build template.

| Module | Responsibility |
|---|---|
| `constants.py` | Named class, field, type, function and comparison IDs |
| `schema.py` | Supported signatures and descriptions, also used for docs |
| `profiles.py` | Versioned framing/function profiles, starting with AoW4 2.3.x |
| `expressions.py`, `api.py` | Typed immutable source tree and readable wrappers |
| `resources.py`, `resource_schemas/*.json` | Named recipes and observed structural defaults |
| `compiler.py` | Native node records, slots and fresh deterministic node identities |
| `formats/binary.py` | Bounded field-table and counted-string codecs |
| `formats/rpk.py` | Observed pack/store wrappers and resource records |
| `formats/acp.py` | Observed project wrapper |
| `content.py`, `content_definitions/*.json` | Extensible named refs and DLC declarations |
| `compatibility.py` | Baseline version and warning/report logic |
| `localization.py` | Simple MO writer |
| `project.py` | Whole-project validation, artifacts, manifests and ZIP |
| `cli.py` | Explicit source loading and commands |
| `drift.py` | Read-only snapshots and update-review comparisons |

## ID categories

Do not conflate these numbers:

- A class ID such as `ClassId.TRIGGER` selects an engine serialization class.
- A field ID is meaningful within a specific owning class/table.
- A function ID is meaningful within its trigger data-type group.
- A resource ID identifies one authored or native definition.
- A UUID identifies the mod project and seeds stable owned resource/node IDs.
- A Workshop ID identifies a published Steam item, not its binary format.

For example `ActionFunction.ADD_TRANSFORMATION` is function 217 of the Action
group. It is not a memory address, a resource ID or an arbitrary opcode guess.

## Opaque profile data

Some small header/editor fields are observed framing defaults whose full
semantics are not known. They use names such as `PROFILE_29`, with comments,
instead of misleading names. The low-level reader preserves unknown fields
and parsed directory ordering inside supported layouts.

This does not promise support for every possible content-store header or future
class. New signatures should be checked, not accepted just because they look
similar. The container reader and semantic compiler are separate layers.

## Determinism

Owned trigger IDs derive from the mod UUID and stable trigger key. Each emitted
node gets an identity seeded by its parent and sequence. Fixed ZIP timestamps
and sorted members make repeated builds with identical inputs reproducible in
the same tool/runtime environment. Different Python/zlib versions may produce
different compressed bytes; payload hashes remain the primary file check.

## Future reverse export

A later readable export can reuse these containers and named schemas. It should
represent the compiled result and preserve opaque data. It cannot recover source
comments or reconstruct an author's exact original Python/editor workflow.
That work is intentionally outside this first authoring preview.

The next integrated reader/exporter is specified in [the local design proposal](reverse-export-design.md). It is not present in the published 0.1.0a3 binaries.

The first analysis stage is implemented in the local development tree; see
[trigger analysis](trigger-analysis.md). Strict trigger-scoped Python export is now implemented; see
[the export guide](trigger-python-export.md). Template-free complete RPK export is now available for the supported strategic
subset; see [full RPK export](full-rpk-python-export.md).
