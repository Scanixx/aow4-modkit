"""Public error types shared by the binary and authoring layers."""


class ModKitError(ValueError):
    """Base class for actionable input, format and project errors."""


class FormatError(ModKitError):
    """Bytes do not match a supported binary layout."""


class ValidationError(ModKitError):
    """An authored definition has invalid parameters or references."""
