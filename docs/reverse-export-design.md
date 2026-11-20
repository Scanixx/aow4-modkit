# Integrated RPK reader and Python exporter

Status: local design, November 20, 2026. The first structural/trigger decoder
and readable-outline stage is implemented in 0.1.0a4.dev0; see
[trigger analysis](trigger-analysis.md). Strict trigger-only Python export is now implemented in 0.1.0a4.dev1;
see [the export guide](trigger-python-export.md). Complete resource export remains planned.
Nothing in this development stage has been published.
The public 0.1.0a3 release and its archives remain unchanged.

## Purpose

Add readable RPK analysis and Python export as tools **inside AoW4 ModKit**.
Use the existing CLI, package, format profiles, named function registry and
public authoring API. Do not introduce a second independent serializer or a
separate application that drifts away from the SDK.

The primary goal is to help mod authors migrate their own existing mods into
readable Python and continue development using the public ModKit API. An
authorized maintainer can use the same workflow while preserving the original
credits and license notices. Understanding compiled behavior supports that
migration and maintenance workflow. Export cannot recover an author's
original Python, missing comments, variable names, deleted branches or editor
workflow. Existing serialized comments can be retained. Generated explanations
must be distinguished from original comments.

## Current evidence and missing pieces

- `formats.binary` and `formats.rpk` already parse supported field tables,
  stores and records and preserve unknown field bytes.
- `inspect` currently lists resource metadata, dependencies and field IDs. It
  does not decode behavior or export source.
- The function registry has 105 named entries, including a native-signature
  alias. Reverse lookup must handle aliases explicitly rather than choosing
  whichever dictionary entry happens to be last.
- Ascension and strategic resource recipes cover selected classes. They do not
  establish a schema for every record or every field of those classes.
- The one-off Donate translator demonstrated named Python export for 17 scripts.
  Its exact-input assertions, legacy readers, local research lookup and pinned
  IDs must be removed from a general converter. It is development evidence, not
  a reusable reader to ship unchanged.
- Current authoring constructors always emit particular enabled/active states,
  supported contexts, node slots and container layouts. A converter must check
  those limitations before promising an equivalent rebuild.

## One pipeline with separate outputs

```text
Read-only RPK / optional ACP, MO and author-supplied reference catalogs
    -> bounded container reader
    -> lossless structural representation with provenance
    -> schema-based semantic decoder and reference index
    -> readable report / structured JSON / public-API Python
    -> optional explicit rebuild and independent semantic comparison
```

Raw preservation and semantic interpretation are separate layers. Unknown bytes
are not guessed to be nested tables, strings, links or executable functions.

### 1. Structural representation

Retain the input SHA-256, selected profile, pack metadata/dependency order,
store/group/record positions, class hierarchy, field IDs, table framing, raw
field values and source byte ranges. Where exact range capture is not yet
available, retain the original enclosing bytes and mark the range unresolved.

Each decoded value carries its origin, for example:

```text
store[0]/group[1]/resource[AD04202613000006]/class[474393]/field[4]/choice[1]
```

Preserve resource IDs, URLs and names separately. Do not infer that an index URL
is disposable merely because the numeric ID matches. Node parent IDs and node
identity/hash bytes also remain available for diagnostics.

Unknown structures become explicit `OpaqueField`, `UnknownResource` or
`UnknownNode` entries in the analysis representation. Those are proposed inert
IR types, not new authoring recipes and not permission to hide a whole script
inside `PreservedParameter`.

### 2. Semantic decoding

Decode the four script phases independently: events, conditions, actions and
setups. Preserve native context, once/enabled/active flags, comments, list
profiles, slot numbers, child order, presets and nested branches.

Resolve functions by `(profile, data_type, function_id)`, with an explicit
canonical-name policy for aliases. Validate argument count, native slots and
types. Setup/action counterparts require verified mapping; matching numeric IDs
alone is insufficient. For example, a greater-than comparison cannot be
rewritten as the public integer equality convenience call.

Never flatten nested guards, reorder actions, change iterator depth, replace an
event-pool reference with a player-pool reference, assume condition-list
short-circuiting or cache a live expression result. Display those distinctions
because they explain many otherwise subtle gameplay behaviors.

Decode resource fields through registered, versioned codecs shared with the
authoring schemas. Add reverse adapters for the existing ascension recipes as
well as the schema-backed strategic recipes. An unexpected extra field in a
known class remains visible and blocks strict export if it cannot be retained.

### 3. Reference and localization resolution

Build a local index from the supplied pack(s), optional ACP and explicit catalogs.
Distinguish internal definitions, external references, native overrides and
unresolved targets. Missing references remain identified by ID and original
link metadata; they do not become invented names or fabricated DLC requirements.

Prefer precise catalog kinds; record unresolved kind/DLC/pack information as
unknown. Pack dependency filenames alone do not prove DLC ownership or the
actual origin of every record. Keep catalog data independently extensible.

RPK localized links provide keys and formatter contexts. Actual English strings
need the matching MO catalog. Preserve missing keys and formatter metadata
rather than generating pretend translations. CLB and image conversion are
outside this phase; report external asset dependencies.

## Reading versus rebuilding

Provide two Python export modes:

| Mode | Result | Unsupported data |
|---|---|---|
| Analysis | Readable Python fragments plus a complete report and IR | Clearly marked inert unknowns; no claim that a mod can be built |
| Strict | Public ModKit API source for the selected scope | Fail with exact reasons if equivalent emission is unsupported |

Analysis output uses a name such as `analysis.py`, not a deceptively complete
`mod.py`. It does not contain a ready-to-package `project` object when the pack
is only partially understood. The complete IR remains the authoritative record
of undecoded data; a partial readable export must say what it omits.

Strict export may explicitly retain **known static** fields through documented
`PreservedParameter` values, as Donate currently does. Report their number and
location separately from fully decoded fields. Opaque executable nodes block
strict export. Unknown fields are never silently dropped or replaced by zeros.

An RPK alone is not a complete mod project. It does not reliably establish the
mod UUID, launcher metadata, all localization texts, other packs or assets.
Default to exporting resource registration functions such as
`register_resources(project, references)`. Only generate a complete `mod.py`
when required project context and dependencies are supplied and validated.
Never silently invent a replacement UUID or claim to preserve save references.

Current ModProject output uses supported one-store layouts. Multi-store packs,
unsupported metadata/flags, native overrides and other nonrepresentable states
must be reported and either supported explicitly or rejected by strict mode.

## Readability rules

- Emit `players.victorious()` and other established convenience calls where
  they exactly match the decoded signature. Use `invoke` with named arguments
  for the rest of the supported registry.
- Use symbolic references and a separate catalog instead of scattered numbers.
  Preserve original IDs in the identity/provenance files.
- Split output by resource and script role: initialization, choices, visibility,
  global triggers and registration. Use stable names with short ID suffixes
  when labels collide; sanitize Python keywords and invalid identifiers.
- Give intermediate values meaningful local names derived from their inputs,
  for example `recipient_player` only when that role is established. Otherwise
  use neutral names such as `player_from_event`, not inferred gameplay intent.
- Start with direct structured branches. Do not turn the entire pack into one
  function containing hundreds of numbered temporary variables.
- Extract repeated immutable expressions only when expansion at compilation
  preserves native order and evaluation. Defer higher-level deduplication and
  inferred helper functions until exact export is validated.
- Keep raw hex out of normal control flow. Put explicit static preservation and
  unsupported fields in separate, documented data files.

Illustrative output using the existing API, not a decoded result:

```python
from aow4modkit import Trigger, actions, core, events

first_turn = Trigger(
    key="first_turn",
    events=[events.new_turn()],
    conditions=[core.current_round().equals(1)],
    actions=[actions.log("Hello Realm loaded.")],
    once=True,
)
```

## Proposed package and commands

All names below are proposed; they do not work in 0.1.0a3.

```text
aow4modkit/analysis/
    model.py             # Structural/semantic IR and format version
    reader.py            # Bounded parsing and source provenance
    triggers.py          # Trigger/node decoder
    resources.py         # Resource adapter registry
    references.py        # Pack/catalog lookup and unresolved references
    diagnostics.py       # Coverage and unsupported-state reports
    python_export.py     # Deterministic AST-based public-API source emission
    compare.py           # Independent normalized comparisons
```

```powershell
python -m aow4modkit inspect Example.rpk --detail
python -m aow4modkit decode Example.rpk --output analysis
python -m aow4modkit export-python Example.rpk --mode analysis --output readable
python -m aow4modkit export-python Example.rpk --mode strict --project Example.acp --output source
```

The existing metadata-only `inspect` output remains compatible. Design a stable
IR JSON schema and diagnostics codes before exposing the new Python API.
Initial candidates are `read_pack`, `decode_pack`, `export_python` and
`compare_decoded`; their exact signatures follow the first implementation.

Expected output includes `inventory.json`, `decoded.json`, `report.md`,
`identities.json`, reference catalogs, script/resource modules and explicit
`preserved/` data only where needed. Reports distinguish decoded/unsupported
resources, fields and executable nodes. Never advertise full coverage based
only on resource counts while ignoring unknown fields inside known resources.

## Verification levels

1. **Structural preservation:** retain raw bytes and framing for the supported
   input container. Compare against the original input, not only a newly
   serialized representation of itself. A copied opaque blob is not semantic
   decoding evidence.
2. **Normalized equivalence:** compare resource identity/metadata, exact known
   values and every script phase, ordered node/argument/list structure, flags,
   comments, choices, references and formatter contexts.
3. **Rebuild:** explicitly compile exported supported source with public API;
   read the result independently and compare its normalized meaning with the
   input. Only framing and generated node identity changes approved by the
   selected profile may be ignored. A plain re-encode need not have the same
   hash as the input; each claimed exception must be listed.
4. **Behavior fixtures:** replay existing Donate and ascension model scenarios
   using decoded/rebuilt graphs. Use independent expected cases, not just the
   same codec on both sides of a round trip.
5. **Engine validation:** later manual editor/game tests; offline success does
   not prove native callbacks, save/Pantheon compatibility or multiplayer.

Every strict export report starts as unverified. Only a completed rebuild
comparison earns the narrower "offline equivalent" result.

## Implementation sequence and acceptance criteria

### Milestone 1: structural IR and trigger decoding

Build the generic decoder using only the SDK reader, profile and registry.
Start with a synthetic Hello Realm fixture, then our two own mods. Support
embedded event scripts as well as top-level triggers. Add exact diagnostics for
unknown functions, extra parameters, disabled nodes and malformed containers.

Accept when all scripts in the two reference mods decode without hard-coded
resource IDs, names, absolute paths or imports from historical tools. Every node
has provenance, and synthetic unknown/disabled cases remain visible.

### Milestone 2: readable analysis and reference graph

Produce Markdown summaries, complete JSON and readable per-script Python.
Show where a trigger runs, what it reads/writes, which guards surround an action
and which resources reference it. Build resource-level reverse references, not
an EXE scanner. Test missing catalogs, colliding names, Unicode and missing MO.

Accept when a reader can follow the Donate selection/transfer flow and the
ascension eligibility/AI startup flow without reading binary field tables.
Partial exports must be obvious and cannot be packaged accidentally.

### Milestone 3: strict public-API export

Add inverse adapters for supported ascension and strategic recipes. Keep pinned
identities, text contexts, choice IDs/modes, dependency order and static
preservation explicit. Supply project context from ACP/metadata where available.

Accept when Hello Realm and the supported scopes of our own mods export and
rebuild in an isolated wheel environment with no legacy tools or game install.
Compare against the published mod reference baselines and rerun all existing
behavior scenarios. Unsupported layouts must fail with useful diagnostics.

### Milestone 4: broaden independently defined schemas

Extend supported classes and functions using small, permission-appropriate
examples. Add generic inverse codecs when a verified schema supports them;
custom adapters remain explicit for classes with special behavior. New DLC
reference catalogs remain separate from engine format profiles.

An unfamiliar mod is an input to understand, not justification to silently
enable an unsupported schema or include someone else's full assets in the SDK.

## Input handling and distribution

Parse RPK as data; never execute extracted or embedded code. Generated source
uses Python AST/constants and fixed SDK imports, not unescaped string injection.
Do not auto-run the exported Python during inspection. An explicit rebuild is
a separate operation on generated, reviewable source.

Bound input size, cumulative decoded bytes, table/node count and nesting depth.
Use iterative traversal where practical. Reject malformed offsets and duplicate
slots without guessing. For future ZIP/mod-folder input, reject path traversal
and do not write into input or installed game folders. Start with direct RPK
input to avoid unnecessary archive complexity.

Outputs go to a new or recognized owned directory. Do not overwrite unrelated
files, follow output links outside that directory or change the input. Emit
basenames/relative provenance by default; omit personal absolute paths from
reports intended for sharing.

The SDK distribution contains code, public schemas, documentation and synthetic
fixtures. Local full-mod fixtures and game-derived assets stay outside it.
Generated reports may contain an input author's strings and data; distinguish
tool licensing from rights in the input and exported content, and retain
attribution. No automatic Workshop download, redistribution or publishing.

## Release plan

Keep the public 0.1.0a3 release immutable. Start as a local development feature
within the current ModKit source, then assign the next preview version when the
implemented scope is known. Do not claim a universal decompiler in that release.
Documentation and CLI help must list supported classes, profile and limitations.

First implementation target: **Milestone 1**, followed by a readable Donate
trigger export. A complete-mod export is a later acceptance target, not a
prerequisite for a useful reader.

## Local implementation update

Version 0.1.0a4.dev2 now supports template-free complete RPK construction for
the initial strategic-resource subset. See [full RPK export](full-rpk-python-export.md)
for the strict class/metadata scope and remaining explicitly preserved static fields.

## Static-structure implementation update

Local 0.1.0a4.dev3 replaces all nine formerly preserved Donate static fields with
[typed native values](native-static-values.md). Exact field-byte reconstruction is verified.
Unknown numeric meanings retain neutral field names; nonempty text formatter metadata
remains separate. The earlier progress sections record historical milestones.

## Text-context implementation update

Local 0.1.0a4.dev4 replaces the Donate resource/notification context hex with
[typed text contexts](text-contexts.md). All 16 unique context values roundtrip
exactly; translations and runtime variable pools remain separate concerns.
