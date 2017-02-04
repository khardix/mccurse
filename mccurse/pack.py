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


# Mod list schema
modlist_schema = {
    'type': 'list',
    'default_setter': lambda doc: list(),
    'schema': {
        'validator': crb.instance_of(File),
        'coerce': crb.fromyaml(File),
    }
}

# Pack files schema
cerberus.schema_registry.add('pack-files', {
    'path': {'validator': crb.instance_of(Path), 'coerce': Path, 'required': True},
    'mods': modlist_schema,
    'dependencies': modlist_schema,
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
    files = attr.ib(validator=vld.instance_of(Mapping))

    def __attrs_post_init__(self: 'ModPack'):
        """Validate structure of files.

        Raises:
            ValidationError: On invalid files format.
        """

        schema = cerberus.schema_registry.get('pack-files')
        validator = cerberus.Validator(schema)

        if not validator.validate(self.files):
            msg = _('Mod-pack has invalid files structure')
            raise ValidationError(msg, validator.errors)
        else:
            self.files = validator.document

    @classmethod
    def new(cls: Type['ModPack'], game: Game, path: Path) -> 'ModPack':
        """Create and initialize a new mod-pack.

        Keyword arguments:
            game: The game to create mod-pack for.
            path: Path to the mods folder, should be relative to the pack's
                location in file system.

        Returns:
            Brand new empty mod-pack.
        """

        return cls(game=game, files={'path': path})


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
