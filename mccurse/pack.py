"""Mod-pack file format interface."""

from collections import OrderedDict
from pathlib import Path
from typing import Mapping, TextIO, Type

import attr
import cerberus
from attr import validators as vld

from . import _
from .addon import File
from .curse import Game
from .util import yaml, cerberus as crb


# Pack structure for validation
modlist = {
    'type': 'list',
    'schema': {'validator': crb.instance_of(File)},
    'default_setter': lambda doc: list(),
}
cerberus.schema_registry.add('pack', {
    'game': {'validator': crb.instance_of(Game), 'required': True},
    'files': {'type': 'dict', 'required': True, 'schema': {
        'path': {'type': 'string', 'required': True},
        'mods': modlist,
        'dependencies': modlist,
    }},
})


class ValidationError(ValueError):
    """Exception for reporting invalid pack data."""

    __slots__ = 'errors',

    def __init__(self, msg: str, errors: dict):
        super().__init__(msg)
        self.errors = errors


@attr.s(slots=True)
class ModPack:
    """Interface to single mod-pack data."""

    game = attr.ib(validator=vld.instance_of(Game))
    path = attr.ib(validator=vld.instance_of(Path))
    mods = attr.ib(
        validator=vld.optional(vld.instance_of(OrderedDict)),
        default=attr.Factory(OrderedDict),
    )
    dependencies = attr.ib(
        validator=vld.optional(vld.instance_of(OrderedDict)),
        default=attr.Factory(OrderedDict),
    )

    @classmethod
    def load(cls: Type['ModPack'], stream: TextIO) -> 'ModPack':
        """Load mod-pack data from a file stream.

        Keyword arguments:
            stream: The text stream to load the data from.

        Returns:
            Loaded mod-pack.
        """

        return cls(**yaml.load(stream))

    def dump(self: 'ModPack', stream: TextIO) -> None:
        """Serialize self to a file stream.

        Keyword arguments:
            stream: The text stream to serialize into.
        """

        yaml.dump(attr.asdict(self, recurse=False), stream)


def resolve(root: File, pool: Mapping[int, File]) -> OrderedDict:
    """Fully resolve dependecies of a root :class:`addon.File`.

    Keyword arguments:
        root: The `addon.File` to resolve dependencies for.
        pool: Available potential dependencies. Mapping from mod identification
            to corresponding file.

    Returns:
        Ordered mapping of all the dependencies, in breadth-first order,
        including the root.
    """

    # Result – resolved dependencies
    resolved = OrderedDict()
    resolved[root.mod.id] = root
    # Which mods needs to be checked
    queue = list(root.dependencies)

    for dep_id in queue:
        if dep_id in resolved:
            continue

        # Get the dependency
        dependency = pool[dep_id]
        # Mark its dependencies for processing
        queue.extend(dependency.dependencies)
        # Add the dependency to chain
        resolved[dep_id] = dependency

    return resolved
