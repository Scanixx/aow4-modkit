"""Typed static values observed in the Age of Wonders 4 2.3 resource profile.

These are build-time data, not game scripts. Names containing ``native_field``
identify a verified storage position whose gameplay meaning is still unknown.
Readers reject extra fields; they never hide them in an opaque byte payload.
"""
from dataclasses import dataclass, fields
import math
import struct

from .errors import ValidationError
from .expressions import ResourceHandle, ResourceLink
from .formats.binary import FieldTable, U32, U64, encode_string, decode_string

HANDLE_CLASS = 0x40004A
TARGETER_BINDING_CLASS = 0x470221
TARGETER_SELECTOR_CLASS = 0x471817
TEXT_CONTEXT_CLASS = 0x401604
ARMY_CONDITIONS_CLASS = 0x476E8A
ATLAS_REGION_CLASS = 0x040112C2
ATLAS_VECTOR_CLASS = 0x04011309


def _table(values, narrow=0):
    return FieldTable(values, narrow_count=narrow).write()


def _read(raw, keys):
    values = FieldTable.read(raw).fields
    if set(values) != set(keys):
        raise ValidationError(f"Unsupported native fields: expected {sorted(keys)}, found {sorted(values)}")
    return values


def _uint(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValidationError("Native integer must fit unsigned 32 bits")
    return U32.pack(value)


def _integer(raw):
    if len(raw) != 4:
        raise ValidationError("Native integer must occupy four bytes")
    return U32.unpack(raw)[0]


class NativeValue:
    """Base for supported static data encoders; subclasses expose all values."""


@dataclass(frozen=True)
class ResourceHandleList(NativeValue):
    """Ordered lightweight references; compact selects native table framing."""
    handles: tuple = ()
    compact: bool = True

    def encode(self, context=None):
        if type(self.compact) is not bool:
            raise ValidationError("compact must be bool")
        rows = {}
        for index, handle in enumerate(self.handles):
            if context is not None and not isinstance(handle, ResourceHandle):
                handle = context.resolve(handle)
            if not isinstance(handle, (ResourceHandle, ResourceLink)):
                raise ValidationError("Handle list needs ResourceHandle or declared resource references")
            if context is not None and isinstance(handle, ResourceHandle) and not context.serialized_links:
                raise ValidationError("Bare handles require explicit serialized-link context")
            rows[index] = U32.pack(HANDLE_CLASS) + _table({20: U64.pack(handle.resource_id),
                22: encode_string(handle.name)}, 2 if self.compact else 0)
        narrow = len(rows) if self.compact else 0
        return _table({30: _table({1: _table(rows, narrow)}, int(self.compact))}, int(self.compact))

    @classmethod
    def decode(cls, raw):
        rows = FieldTable.read(_read(_read(raw, {30})[30], {1})[1]).fields
        if list(rows) != list(range(len(rows))):
            raise ValidationError("Handle list indices must be consecutive")
        handles = []
        for blob in rows.values():
            if len(blob) < 4 or U32.unpack_from(blob)[0] != HANDLE_CLASS:
                raise ValidationError("Unsupported handle class")
            row = _read(blob[4:], {20,22})
            if len(row[20]) != 8:
                raise ValidationError("Handle ID must occupy eight bytes")
            handles.append(ResourceHandle(U64.unpack(row[20])[0], decode_string(row[22])))
        return cls(tuple(handles), bool(FieldTable.read(raw).narrow_count))


@dataclass(frozen=True)
class EmptyTextContext(NativeValue):
    """Native empty localized value, including its empty formatter context."""
    def encode(self, context=None):
        return _table({2: _table({TEXT_CONTEXT_CLASS: _table({0: _table({1: _table({})},1)},1)})},1)

    @classmethod
    def decode(cls, raw):
        inner = _read(_read(_read(_read(raw,{2})[2],{TEXT_CONTEXT_CLASS})[TEXT_CONTEXT_CLASS],{0})[0],{1})
        _read(inner[1],set())
        return cls()


@dataclass(frozen=True)
class StrategicTargeterBinding(NativeValue):
    targeters: ResourceHandleList
    native_selector_value: int = 1537

    def encode(self, context=None):
        record = U32.pack(TARGETER_BINDING_CLASS) + _table({3: self.targeters.encode(context),
            TARGETER_SELECTOR_CLASS: _uint(self.native_selector_value)},1)
        return _table({1: record, 2: U32.pack(TARGETER_BINDING_CLASS)},2)

    @classmethod
    def decode(cls, raw):
        outer = _read(raw,{1,2})
        if _integer(outer[2]) != TARGETER_BINDING_CLASS or _integer(outer[1][:4]) != TARGETER_BINDING_CLASS:
            raise ValidationError("Unsupported targeter binding class")
        row = _read(outer[1][4:],{3,TARGETER_SELECTOR_CLASS})
        return cls(ResourceHandleList.decode(row[3]),_integer(row[TARGETER_SELECTOR_CLASS]))


@dataclass(frozen=True)
class UnitRequisiteFilter(NativeValue):
    """Three native requisite lists; matching-mode semantics remain unverified."""
    native_field_3: ResourceHandleList = ResourceHandleList()
    native_field_4: ResourceHandleList = ResourceHandleList()
    native_field_5: ResourceHandleList = ResourceHandleList()

    def encode(self, context=None):
        return _table({k:getattr(self,f"native_field_{k}").encode(context) for k in (3,4,5)},3)

    @classmethod
    def decode(cls, raw):
        row = _read(raw,{3,4,5})
        return cls(*(ResourceHandleList.decode(row[k]) for k in (3,4,5)))


@dataclass(frozen=True)
class ArmyTargetConditions(NativeValue):
    native_field_2: ResourceHandleList = ResourceHandleList()
    native_field_3: ResourceHandleList = ResourceHandleList()
    native_field_4: ResourceHandleList = ResourceHandleList()
    native_field_7: ResourceHandleList = ResourceHandleList()
    native_field_8: int = 513
    native_field_1: int = 1

    def encode(self, context=None):
        row = {k:getattr(self,f"native_field_{k}").encode(context) for k in (2,3,4,7)}
        row.update({8:_uint(self.native_field_8),1:_uint(self.native_field_1)})
        return _table({ARMY_CONDITIONS_CLASS:_table(row,5)})

    @classmethod
    def decode(cls, raw):
        row = _read(_read(raw,{ARMY_CONDITIONS_CLASS})[ARMY_CONDITIONS_CLASS],{1,2,3,4,7,8})
        return cls(*(ResourceHandleList.decode(row[k]) for k in (2,3,4,7)),
                   _integer(row[8]),_integer(row[1]))


@dataclass(frozen=True)
class AtlasSpriteReference(NativeValue):
    atlas_path: str
    region_name: str
    native_field_21: int = 1

    def encode(self, context=None):
        return _table({20:_table({20:encode_string(self.atlas_path),23:encode_string(self.region_name)}),
                       21:_uint(self.native_field_21)},2)

    @classmethod
    def decode(cls, raw):
        row = _read(raw,{20,21}); ref = _read(row[20],{20,23})
        return cls(decode_string(ref[20]),decode_string(ref[23]),_integer(row[21]))


@dataclass(frozen=True)
class EnvironmentReference(NativeValue):
    path: str
    name: str

    def encode(self, context=None):
        return _table({20:encode_string(self.path),23:encode_string(self.name)},2)

    @classmethod
    def decode(cls, raw):
        row = _read(raw,{20,23})
        return cls(decode_string(row[20]),decode_string(row[23]))


@dataclass(frozen=True)
class AtlasRenderParameters(NativeValue):
    """Observed float32 vector and scalar; their rendering meaning is unknown."""
    native_vector_0: tuple = (0.0,0.0,5.0)
    native_scalar_3: float = 0.8

    def encode(self, context=None):
        values = (*self.native_vector_0,self.native_scalar_3)
        if len(values) != 4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in values):
            raise ValidationError("Atlas parameters need three finite vector values and one finite scalar")
        return _table({ATLAS_VECTOR_CLASS:_table({0:struct.pack('<3f',*self.native_vector_0),
                                                3:struct.pack('<f',self.native_scalar_3)},2)})

    @classmethod
    def decode(cls, raw):
        row = _read(_read(raw,{ATLAS_VECTOR_CLASS})[ATLAS_VECTOR_CLASS],{0,3})
        if len(row[0]) != 12 or len(row[3]) != 4:
            raise ValidationError("Unsupported atlas float32 widths")
        result = cls(struct.unpack('<3f',row[0]),struct.unpack('<f',row[3])[0])
        result.encode()  # Reject nonfinite values rather than emit invalid Python.
        return result


@dataclass(frozen=True)
class TextureAtlasRegion(NativeValue):
    sprite: AtlasSpriteReference
    render_profile: ResourceLink
    environment: EnvironmentReference
    render_parameters: AtlasRenderParameters = AtlasRenderParameters()
    native_flag_54: bool = False

    def encode(self, context=None):
        if type(self.native_flag_54) is not bool:
            raise ValidationError("Atlas flag must be bool")
        ref = context.resolve(self.render_profile) if context is not None else self.render_profile
        row = {20:encode_string(ref.url),22:U64.pack(ref.resource_id),23:encode_string(ref.name)}
        return _table({ATLAS_REGION_CLASS:_table({0:self.sprite.encode(context),50:_table(row,3),
            51:self.environment.encode(context),53:self.render_parameters.encode(context),
            54:bytes([self.native_flag_54])},5)})

    @classmethod
    def decode(cls, raw):
        row = _read(_read(raw,{ATLAS_REGION_CLASS})[ATLAS_REGION_CLASS],{0,50,51,53,54})
        ref = _read(row[50],{20,22,23})
        if len(ref[22]) != 8 or row[54] not in (b'\0',b'\1'):
            raise ValidationError("Unsupported atlas reference or flag width")
        return cls(AtlasSpriteReference.decode(row[0]),
            ResourceLink(U64.unpack(ref[22])[0],decode_string(ref[23]),decode_string(ref[20])),
            EnvironmentReference.decode(row[51]),AtlasRenderParameters.decode(row[53]),bool(row[54][0]))


NATIVE_TYPES = {cls.__name__:cls for cls in (ResourceHandleList,EmptyTextContext,
    StrategicTargeterBinding,UnitRequisiteFilter,ArmyTargetConditions,AtlasSpriteReference,
    EnvironmentReference,AtlasRenderParameters,TextureAtlasRegion)}


def native_description(value):
    """JSON-safe constructor tree used by strict inverse recipes and comparison."""
    if isinstance(value,(NativeValue,ResourceHandle,ResourceLink)):
        return dict(native_type=type(value).__name__,arguments={f.name:native_description(getattr(value,f.name)) for f in fields(value)})
    if isinstance(value,tuple):
        return [native_description(item) for item in value]
    return value
