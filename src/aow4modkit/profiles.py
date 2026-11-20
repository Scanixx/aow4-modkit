"""Versioned observed format profiles, separate from DLC content catalogs.

An added profile is an explicit engineering decision, not automatic acceptance
of unknown data. Fundamental field-table/class changes still need a new adapter
and tests. Keep older profiles so their artifacts remain reproducible.
"""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .schema import FUNCTIONS, FunctionSpec
from .errors import ValidationError


@dataclass(frozen=True)
class GameProfile:
    key: str
    game_series: str
    rpk_signature: bytes
    rpk_header_size: int
    rpk_name_offset: int
    rpk_name_capacity: int
    rpk_length_offset: int
    store_headers: tuple[bytes, ...]
    acp_prefix: bytes
    acp_class_offset: int
    acp_class_signature: bytes
    functions: Mapping[str, FunctionSpec] = field(default_factory=lambda: MappingProxyType(dict(FUNCTIONS)))


DEFAULT_PROFILE = GameProfile(
    key="aow4-2.3-observed-v1", game_series="2.3.*",
    rpk_signature=bytes.fromhex("52504b001a000004"),
    rpk_header_size=176, rpk_name_offset=16, rpk_name_capacity=128, rpk_length_offset=12,
    store_headers=(bytes.fromhex("7f010004023200330440000000"),
                   bytes.fromhex("72010004023200330441000000"),
                   bytes.fromhex("74010004023200330442000000")),
    acp_prefix=bytes.fromhex("435052000000000000000000000000000100009d00400080010000009d00400000000000"),
    acp_class_offset=19, acp_class_signature=bytes.fromhex("9d004000"),
)
PROFILES = {DEFAULT_PROFILE.key: DEFAULT_PROFILE}


def get_profile(key: str) -> GameProfile:
    try:
        return PROFILES[key]
    except KeyError as exc:
        raise ValidationError(f"Unknown game profile: {key}; inspect and verify new formats before adding one") from exc
