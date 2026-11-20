"""Readable localized-text storage for the observed Age of Wonders 4 2.3 profile.

This module encodes keys and formatter metadata, not MO translations. Stored
formatter values are retained without assuming they are current gameplay costs.
"""
from dataclasses import dataclass
from enum import Enum

from .errors import ValidationError
from .formats.binary import FieldTable, U32, encode_string, decode_string

TEXT_FORMAT_CONTEXT_CLASS = 0x401604
TEXT_SUBSTITUTION_CLASS = 0x401602


class TextContextStyle(str, Enum):
    FORMATTED = "formatted"
    DIALOG = "dialog"
    KEY_ONLY = "key_only"


def _table(values, narrow=0):
    return FieldTable(values,narrow_count=narrow).write()


def _read(raw, keys):
    values=FieldTable.read(raw).fields
    if set(values) != set(keys):
        raise ValidationError(f"Unsupported localized fields: expected {sorted(keys)}, found {sorted(values)}")
    return values


def _empty_list():
    return _table({1:_table({})},1)


def _check_empty_list(raw):
    _read(_read(raw,{1})[1],set())


def _compact_rows(rows):
    # Native lists can mix narrow and wide entries once payload offsets exceed
    # a byte. FieldTable's all-or-nothing fallback is not appropriate here.
    offset=0; narrow=0
    for key,value in rows.items():
        if key > 255 or offset > 255 or narrow == 127:
            break
        narrow += 1; offset += len(value)
    return _table(rows,narrow)


@dataclass(frozen=True)
class TextSubstitution:
    """Recorded formatter token and optional native string value (fields 2/3).

    An absent value and an explicitly empty value are distinct. This type does
    not evaluate hyperlinks or infer whether a value is cached or overridden.
    """
    token: str
    value: str | None = None

    def __post_init__(self):
        if not isinstance(self.token,str) or not self.token or (self.value is not None and not isinstance(self.value,str)):
            raise ValidationError("TextSubstitution needs a token and an optional string value")

    def encode(self):
        fields={2:encode_string(self.token)}
        if self.value is not None:fields[3]=encode_string(self.value)
        return U32.pack(TEXT_SUBSTITUTION_CLASS)+_table({TEXT_SUBSTITUTION_CLASS:_table(fields,len(fields))})

    @classmethod
    def decode(cls,raw):
        if len(raw)<4 or U32.unpack_from(raw)[0] != TEXT_SUBSTITUTION_CLASS:
            raise ValidationError("Unsupported text substitution class")
        row=FieldTable.read(_read(raw[4:],{TEXT_SUBSTITUTION_CLASS})[TEXT_SUBSTITUTION_CLASS]).fields
        if set(row) not in ({2},{2,3}):
            raise ValidationError("Unsupported text substitution fields")
        return cls(decode_string(row[2]),decode_string(row[3]) if 3 in row else None)


@dataclass(frozen=True)
class TextContext:
    """Typed native text layout, used as LocalizedText.context.

    FORMATTED stores formatter entries; DIALOG adds the observed dialog wrapper
    and empty auxiliary list; KEY_ONLY stores a key without formatter metadata.
    compact controls only the outer key/wrapper directory, not game behavior.
    """
    style: TextContextStyle = TextContextStyle.FORMATTED
    substitutions: tuple[TextSubstitution,...] = ()
    compact: bool = True

    def __post_init__(self):
        if not isinstance(self.style,TextContextStyle) or type(self.compact) is not bool:
            raise ValidationError("TextContext needs a TextContextStyle and boolean compact flag")
        if not isinstance(self.substitutions,tuple) or any(not isinstance(v,TextSubstitution) for v in self.substitutions):
            raise ValidationError("TextContext substitutions must be a tuple of TextSubstitution values")
        if self.style == TextContextStyle.KEY_ONLY and self.substitutions:
            raise ValidationError("Key-only text cannot have formatter substitutions")

    @classmethod
    def notification(cls):
        """Observed wide-directory key-only notification text layout."""
        return cls(TextContextStyle.KEY_ONLY,compact=False)

    def encode(self,key):
        if not isinstance(key,str) or not key:
            raise ValidationError("Localized key must be a nonempty string")
        if self.style == TextContextStyle.KEY_ONLY:
            return _table({1:encode_string(key)},int(self.compact))
        rows={index:value.encode() for index,value in enumerate(self.substitutions)}
        metadata=_table({TEXT_FORMAT_CONTEXT_CLASS:_table({0:_table({1:_compact_rows(rows)},1)},1)})
        fields={1:encode_string(key),2:metadata}
        inner=_table(fields,2 if self.style == TextContextStyle.DIALOG else 2*int(self.compact))
        if self.style == TextContextStyle.DIALOG:
            return _table({0:inner,1:_empty_list()},2*int(self.compact))
        return inner

    @classmethod
    def decode(cls,raw):
        """Return (catalog_key, context), rejecting unknown structure/fields."""
        root=FieldTable.read(raw); row=root.fields; compact=bool(root.narrow_count)
        if set(row)=={1}:
            return cls._checked_key(row[1]),cls(TextContextStyle.KEY_ONLY,compact=compact)
        style=TextContextStyle.FORMATTED
        if set(row)=={0,1}:
            style=TextContextStyle.DIALOG
            _check_empty_list(row[1]); row=_read(row[0],{1,2})
        if set(row)!={1,2}:
            raise ValidationError("Unsupported localized key/context layout")
        formatter=_read(row[2],{TEXT_FORMAT_CONTEXT_CLASS})[TEXT_FORMAT_CONTEXT_CLASS]
        rows=FieldTable.read(_read(_read(formatter,{0})[0],{1})[1]).fields
        if list(rows)!=list(range(len(rows))):
            raise ValidationError("Text substitution indices must be consecutive")
        return cls._checked_key(row[1]),cls(style,tuple(TextSubstitution.decode(v) for v in rows.values()),compact)

    @staticmethod
    def _checked_key(raw):
        key=decode_string(raw)
        if not key:raise ValidationError("Localized key must not be empty")
        return key


def text_description(key,context):
    """Readable JSON-safe values for inverse recipe comparison and generation."""
    return dict(key=key,style=context.style.value,compact=context.compact,
                substitutions=[dict(token=v.token,value=v.value) for v in context.substitutions])
