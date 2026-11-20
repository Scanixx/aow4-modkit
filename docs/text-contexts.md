# Typed text and notification contexts

Local development API added in 0.1.0a4.dev4 for the observed 2.3 profile.
`LocalizedText` identifies a catalog key. `TextContext` describes its native
layout and formatter entries; `TextSubstitution` describes an individual entry.
English or other translated strings still live in the MO catalog.

## Public API

```python
from aow4modkit import LocalizedText, TextContext, TextContextStyle, TextSubstitution

title = LocalizedText("EXAMPLE@SPELL@NAME", context=TextContext())

description = LocalizedText(
    "EXAMPLE@SPELL@DESCRIPTION",
    context=TextContext(substitutions=(
        TextSubstitution(token="{GLOBAL.Example.Hyperlink}"),
        TextSubstitution(token="{amount}", value="2 [example/]"),
    )),
)

dialog_title = LocalizedText(
    "EXAMPLE@EVENT@TITLE",
    context=TextContext(style=TextContextStyle.DIALOG),
)

notification_title = LocalizedText(
    "EXAMPLE@RECEIPT@TITLE", context=TextContext.notification(),
)
```

Use these values in resource recipes or in the existing
`localized_link(notification_title)` expression when a trigger argument needs
a localized string link. Python constructs native data at build time; the game
does not execute this Python module.

`TextContextStyle.FORMATTED` is the ordinary key-plus-formatter layout.
`DIALOG` adds the observed dialog wrapper and empty auxiliary list. `KEY_ONLY`
stores only the key, as used by Donate's notification title/body.
`TextContext.notification()` selects `KEY_ONLY` with a wide field directory,
matching those observed notification contexts. These are storage forms, not a
complete classification of every possible game UI text.

`compact` controls outer directory framing, not formatting semantics. The
serializer also constructs mixed narrow/wide formatter-list directories when
entry offsets exceed one byte. Substitutions retain their order and duplicates.
An absent `value=None` and an explicit empty `value=""` remain distinct.

`LocalizedText(key)` without a context keeps its existing profile default.
`LocalizedText(key, context=legacy_bytes)` remains accepted for older authored
projects. New strict inverse export expects supported structured layouts and
rejects unknown formatter data rather than hiding it as a hex payload.

## Storage structure

Constants are named in `aow4modkit.text_contexts`:

| Constant | Value | Observed role |
| --- | --- | --- |
| `TEXT_FORMAT_CONTEXT_CLASS` | `0x00401604` | Class field containing the formatter list wrapper |
| `TEXT_SUBSTITUTION_CLASS` | `0x00401602` | Entry record and its class field |

The formatted layout has key field 1 and metadata field 2. Inside the metadata,
the context class contains field 0, then list field 1 and indexed entries.
Each entry has the substitution class prefix and class table. Its field 2 is
the counted UTF-8 token; optional field 3 is the recorded string value.

The dialog layout wraps that formatted value in field 0 and stores an empty
auxiliary list in field 1. Key-only text contains field 1 and no formatter
metadata. Readers validate exact field sets, class IDs, list indices and UTF-8
lengths. Unsupported auxiliary data, extra fields or classes fail explicitly.

`TextContext.decode(raw)` returns `(key, context)`.
`context.encode(key)` constructs native bytes from those values. The key is
provided at encoding time, so changing `LocalizedText.key` does not reuse an
old serialized key. These methods do not read game files or resolve translations.

## Generated source

Both full-RPK and trigger-only exports now produce `localized_texts.py` for
script notification text. Full-RPK export additionally produces
`resource_texts.py` for recipe/dialog text. Each module contains a `TEXTS`
dictionary of public `LocalizedText`/`TextContext`/`TextSubstitution` objects.
Generated builders load these modules explicitly when a trusted build is run.

`localized-links.json` and `resource-texts.json` are readable snapshots with
`key`, `style`, `compact` and `substitutions` fields. They contain no
`context_hex` and are not the build source. Edit the Python definitions to
change a generated mod. Manifest file hashes describe the initial export.
The analysis decoder may still retain original bytes as provenance; that
provenance is not needed by the template-free build.

## Donate observations and limits

The complete Donate export has 14 distinct resource text contexts and two
notification text contexts. Two resource definitions use the same description
key with different formatter metadata; they remain separate definitions.

Observed formatter entries include global hyperlink tokens, stored mana/casting
strings and a stored vision string inherited from source templates. They are
preserved exactly. Their presence does not establish the spell's actual cost,
vision effect or other current gameplay behavior. This API exposes recorded
strings without evaluating whether an individual value is cached or overridden.

Donate's two notification contexts are key-only. The sender/unit names are
provided separately by existing trigger variable-pool operations and referenced
by the MO message placeholders. They are not additional hidden formatter values
inside the notification contexts. Text context support does not change transfer
logic, variable lifetime, notification icons, locations or translations.

All 16 original context values reconstruct byte for byte. The complete RPK
matches the previous SDK build byte for byte; the independent historical reader
also confirms reference resource/script equivalence and all 41 model cases.
An extracted-wheel build needs no original RPK. No new engine test is implied.
