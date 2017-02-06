"""Mod-pack file format interface."""

import os
from collections import OrderedDict, ChainMap
from pathlib import Path
from typing import Mapping, TextIO, Type, Generator, Iterable

import attr
import cerberus
import requests
from attr import validators as vld

from . import _
from .addon import File
from .exceptions import InvalidStream
from .curse import Game
from .util import yaml, cerberus as crb, default_new_session


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
            msg = _('Modpack file contains invalid data'), validator.errors
            raise InvalidStream(*msg)
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

    def fetch(self: 'ModPack', file: File, *, session: requests.Session = None):
        """Fetch file from the Curse CDN, if it not already exists in the target directory.

        Keyword arguments:
            path -- The target directory to store the file to.
            session -- The session to use for downloading the file.

        Raises:
            OSerror: Path do not exists or is not a directory.
            requests.HTTPerror: On HTTP errors.
        """

        session = default_new_session(session)

        if not self.path.is_dir():
            raise NotADirectoryError(str(self.path))

        target = self.path / file.name
        # Skip up-to-date files
        if target.exists() and target.stat().st_mtime == file.date.timestamp():
            return target

        remote = session.get(file.url)
        remote.raise_for_status()

        target.write_bytes(remote.content)
        os.utime(str(target), times=(file.date.timestamp(),)*2)

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

    def orphans(self: 'ModPack') -> Iterable[File]:
        """Finds all no longer needed dependencies.

        Yields:
            Orphaned files.
        """

        # Construct full dependency chain
        available = ChainMap(self.mods, self.dependencies)
        needed = {}
        for file in self.mods.values():
            needed.update(resolve(file, pool=available))

        # Filter unneeded dependencies
        yield from (
            file for m_id, file in self.dependencies.items()
            if m_id not in needed
        )


@attr.s(slots=True)
class FileChange:
    """File change within a mod-pack, both in metadata and on file system."""

    #: ModPack to be changed
    pack = attr.ib(validator=vld.instance_of(ModPack))
    #: Source metadata storage
    source = attr.ib(validator=vld.optional(vld.instance_of(OrderedDict)))
    #: Old file, which should be removed from file system and source storage
    old_file = attr.ib(validator=vld.optional(vld.instance_of(File)))
    #: Destination metadata storage
    destination = attr.ib(validator=vld.optional(vld.instance_of(OrderedDict)))
    #: New file, which should be added to the file system and destination storage
    new_file = attr.ib(validator=vld.optional(vld.instance_of(File)))

    # Path properties

    @property
    def old_path(self):
        """Full path to the old file."""
        if self.old_file is None:
            return None
        else:
            return self.pack.path / self.old_file.name

    @property
    def new_path(self):
        """Full path to the new file."""
        if self.new_file is None:
            return None
        else:
            return self.pack.path / self.new_file.name

    @property
    def tmp_path(self):
        """Full path to the old file."""

        if self.old_file is None:
            return None

        tmp_name = '.'.join([self.old_file.name, 'disabled'])
        return self.pack.path / tmp_name


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
