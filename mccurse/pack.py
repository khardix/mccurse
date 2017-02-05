"""Mod-pack file format interface."""

from collections import OrderedDict, ChainMap
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping, TextIO, Type, Generator, Iterable

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
class FileChange:
    """Description of a change inside a ModPack."""

    #: Dictionary with old version of the file
    old_store = attr.ib(validator=vld.instance_of(Mapping))
    #: Dictionary which should receive the new version of the file
    new_store = attr.ib(validator=vld.instance_of(Mapping))
    #: New version of the file
    file = attr.ib(validator=vld.instance_of(File))


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

        validator = cerberus.Validator(cerberus.schema_registry.get('pack'))

        if not validator.validate(yaml.load(stream)):
            msg = _('Modpack file contains invalid data', validator.errors)
            raise ValidationError(msg)
        else:
            data = validator.document
            return cls(
                game=data['game'],
                path=Path(data['files']['path']),
                mods=OrderedDict((d.mod.id, d) for d in data['files']['mods']),
                dependencies=OrderedDict((d.mod.id, d) for d in data['files']['dependencies']),
            )

    def dump(self: 'ModPack', stream: TextIO) -> None:
        """Serialize self to a file stream.

        Keyword arguments:
            stream: The text stream to serialize into.
        """

        data = OrderedDict()
        data['game'] = self.game
        data['files'] = OrderedDict()
        data['files']['path'] = str(self.path)
        data['files']['mods'] = list(self.mods.values())
        data['files']['dependencies'] = list(self.dependencies.values())

        yaml.dump(data, stream)

    @contextmanager
    def replacing(self: 'ModPack', change: FileChange) -> Generator[File, None, None]:
        """Prepare file system for receiving a new file, and cleans up afterwards.

        Keyword arguments:
            change: The file change about to be executed.

        Yields:
            The new file metadata.
        """

        nfile = change.file
        ofile = change.old_store[nfile.mod.id]

        # Temporary rename of the old file
        enabled = self.path / ofile.name
        disabled = enabled.with_suffix('.'.join((enabled.suffix, 'disabled')))

        try:
            enabled.rename(disabled)
            yield nfile
        except:  # Error, remove new file and rename the old back
            self.path.joinpath(nfile.name).unlink()
            disabled.rename(enabled)
        else:  # No error, remove disabled file
            change.new_store[nfile.mod.id] = nfile
            del change.old_store[ofile.mod.id]
            disabled.unlink()

    def filter_obsoletes(
        self: 'ModPack',
        files: Iterable[File]
    ) -> Generator[File, None, None]:
        """Filter obsolete files.

        Obsolete files are defined as being already installed, or being
        an older version of already installed files.

        Keyword arguments:
            files: Iterable of mod :class:`File`s to filter.

        Yields:
            Original files without the obsoletes.
        """

        installed = ChainMap(self.mods, self.dependencies)

        for file in files:
            if file.mod.id not in installed:
                yield file

            current = installed[file.mod.id]
            if file.date > current.date:
                yield file
            else:
                continue


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
