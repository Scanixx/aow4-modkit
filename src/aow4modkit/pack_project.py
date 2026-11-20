"""Template-free native RPK construction from public resource definitions."""
from dataclasses import dataclass
import re
from uuid import UUID

from .compiler import Trigger, TriggerCompiler
from .errors import ValidationError
from .expressions import ResourceRef
from .formats.binary import encode_strings
from .formats.rpk import ResourcePack
from .profiles import DEFAULT_PROFILE, GameProfile
from .resources import ResourceDefinition, ResourceContext


@dataclass
class ResourcePackProject:
    """An explicitly contextualized RPK, not a launcher/whole-mod project.

    All IDs/names and dependency order are explicit. Serialized ResourceLink and
    ResourceHandle values are accepted without claiming their pack/DLC origin.
    The supported profile supplies the container framing; no RPK is read.
    """
    name: str
    mod_id: UUID | str
    definitions: tuple
    dependencies: tuple[str, ...] = ()
    profile: GameProfile = DEFAULT_PROFILE

    def compile(self):
        try:
            identity = self.mod_id if isinstance(self.mod_id, UUID) else UUID(str(self.mod_id))
        except (ValueError, TypeError) as exc:
            raise ValidationError("RPK project requires an explicit valid mod UUID") from exc
        if not isinstance(self.profile, GameProfile):
            raise ValidationError("RPK project needs a registered format profile")
        definitions = tuple(self.definitions)
        if not definitions:
            raise ValidationError("RPK project needs resource definitions")
        if any(not isinstance(d, (Trigger, ResourceDefinition)) or isinstance(d, Trigger) and d.embedded for d in definitions):
            raise ValidationError("Pack definitions must be resources or global triggers")
        keys = [d.key for d in definitions]
        ids = [d.resource_id for d in definitions]
        if any(not isinstance(key,str) or not key for key in keys):
            raise ValidationError("RPK resource keys must be nonempty strings")
        if any(type(uid) is not int or not 0 < uid <= 0xFFFFFFFFFFFFFFFF for uid in ids):
            raise ValidationError("All RPK resource IDs must be pinned explicitly")
        if len(set(keys)) != len(keys) or len(set(ids)) != len(ids):
            raise ValidationError("RPK resource keys and IDs must be unique")
        if any(not isinstance(d.name,str) or not d.name for d in definitions):
            raise ValidationError("All RPK resource names must be explicit")
        dependencies = tuple(self.dependencies)
        if len(set(dependencies)) != len(dependencies) or any(not re.fullmatch(r"[A-Z0-9_-]+\.(RPK|MO|CLB)", dep) for dep in dependencies):
            raise ValidationError("Explicit dependencies must be unique uppercase RPK/MO/CLB filenames")
        bindings = {d.key: ResourceRef(d.resource_id, d.name, f"[#{d.resource_id:016X}]0\\{i}", self.name,
                                     kind="trigger" if isinstance(d, Trigger) else d.kind)
                    for i, d in enumerate(definitions)}
        context = ResourceContext(bindings, self.profile, {d.key:d for d in definitions}, identity,
                                  serialized_links=True)
        records = []
        for index, definition in enumerate(definitions):
            if isinstance(definition, Trigger):
                record = TriggerCompiler(identity, definition.resource_id, self.profile, bindings).compile(
                    definition, resource_id=definition.resource_id, index=index)
            else:
                record = definition.compile(context)
            records.append(record)
        pack = ResourcePack.create(self.name, records, dependencies, profile=self.profile)
        # Native dependency order can matter to an existing pack. Do not infer
        # or silently sort/append origins absent from the provided context.
        pack.table.fields[30] = encode_strings(dependencies)
        pack.verify_roundtrip()
        return pack

    def build(self):
        """Return newly constructed RPK bytes; no input template or file writes."""
        return self.compile().write()
