"""Reverse signatures, including literal getters emitted by the compiler."""
from ..constants import DataType as T
from ..schema import FunctionSpec, Parameter

# These three wrappers are implicit in compiler.literal_profiles, rather than
# public invoke() functions. They are decoded natively, not guessed from names.
LITERAL_READERS = (
    FunctionSpec("literal.integer", T.INTEGER, 0, (Parameter("value", T.INTEGER_PRESET),), "Read an integer preset."),
    FunctionSpec("literal.boolean", T.BOOLEAN, 0, (Parameter("value", T.BOOLEAN_PRESET),), "Read a boolean preset."),
    FunctionSpec("literal.string", T.STRING, 0, (Parameter("value", T.STRING_PRESET),), "Read a string preset."),
)


def reverse_signatures(profile):
    """Keep aliases deterministic; integer comparison supports all operators."""
    entries = {}
    for spec in (*profile.functions.values(), *LITERAL_READERS):
        entries.setdefault((int(spec.data_type), spec.function_id), []).append(spec)
    result = {}
    for wire, variants in entries.items():
        variants.sort(key=lambda spec: (spec.name != "comparisons.integer", spec.name))
        chosen = variants[0]
        if any(spec.parameters != chosen.parameters for spec in variants):
            raise ValueError(f"Inconsistent reverse signature aliases: {wire}")
        result[wire] = chosen, tuple(spec.name for spec in variants[1:])
    # Only the setup counterparts already emitted by the supported compiler.
    for (typ, fid), value in list(result.items()):
        if typ == T.ACTION and 0 <= fid <= 12:
            result[(int(T.SETUP), fid)] = value
    return result
