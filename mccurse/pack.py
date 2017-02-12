"""Mod-pack file format interface."""

import os
from contextlib import suppress, ExitStack
from collections import OrderedDict, ChainMap
from itertools import groupby
from pathlib import Path
from typing import TextIO, Type, Generator, Iterable, Optional, Sequence, Mapping

import attr
import cerberus
import requests
from attr import validators as vld

from . import _, log, exceptions
from .addon import File, Mod, Release
from .curse import Game
from .proxy import latest_file_tree, resolve
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

    @property
    def installed(self):
        """Provides a view into all installed mods (including dependencies)."""
        return ChainMap(self.mods, self.dependencies)

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
            raise exceptions.InvalidStream(*msg)
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

        for file in files:
            current = self.installed.get(file.mod.id, None)

            if current is None or current.date < file.date:
                yield file
            else:
                continue

    def orphans(self: 'ModPack', mods: Mapping[int, Mod]=None) -> Generator[File, None, None]:
        """Finds all no longer needed dependencies.

        Keyword arguments:
            mods: Optional mapping of installed mods [default: self.mods].
                The purpose of this parameter is to be able to override
                really installed mods without changing the property directly.

        Yields:
            Orphaned files.
        """

        if mods is None:
            mods = self.mods

        needed = {}
        for file in mods.values():
            needed.update(resolve(file, pool=self.installed))

        # Filter unneeded dependencies
        yield from (
            file for m_id, file in self.dependencies.items()
            if m_id not in needed
        )

    def apply(
        self: 'ModPack',
        changes: Sequence['FileChange'],
        *,
        session: requests.Session = None
    ) -> None:
        """Applies all provided changes.

        Possible destructive operation, use with care.

        Keyword arguments:
            changes: The changes to be applied.
            session: If there is a change which calls for a new file content,
                use this session to download it.
        """

        session = default_new_session(session)

        with ExitStack() as transaction:
            for change in changes:
                nfile = transaction.enter_context(change)

                # Nothing more to do
                if nfile is None:
                    continue

                # Change is asking for new file; fetch it
                log.info(_('Downloading {0.name}').format(nfile))
                self.fetch(nfile, session=session)

    def install_changes(
        self: 'ModPack',
        mod: Mod,
        min_release: Release,
        session: requests.Session
    ) -> Sequence['FileChange']:
        """Generate all changes necessary for mod installation.

        Keyword arguments:
            mod: The mod to install.
            min_release: Minimal release type to consider for installation.
            session: Authorized requests.Session to use for fetching
                available file information.

        Returns:
            File changes necessary for successful mod installation.

        Raises:
            AlreadyInstalled: The requested mod is already installed.
            NoFilesAvailable: There are no files available for mod-pack's
                version of the game for the specified mod.
        """

        # Do not install already installed mod
        if mod.id in self.mods:
            raise exceptions.AlreadyInstalled(mod.name)
        # On dependency, just mark as explicitly installed
        elif mod.id in self.dependencies:
            return [FileChange.explicit(self, self.dependencies[mod.id])]

        # Brand new mod to install – resolve full tree
        files = latest_file_tree(self.game, mod, min_release, session=session)
        if not files:
            raise exceptions.NoFileFound(mod.name)

        # Filter out obsolete files
        files = self.filter_obsoletes(files)

        # Install file for requested mod into mods
        changes = [FileChange.installation(self, self.mods, next(files))]
        # Install or upgrade dependencies
        for dependency in files:
            if dependency.mod.id in self.installed:
                changes.append(FileChange.upgrade(self, dependency))
            else:
                changes.append(
                    FileChange.installation(self, self.dependencies, dependency)
                )

        return changes

    def remove_changes(self: 'ModPack', mod: Mod) -> Sequence['FileChange']:
        """Generate all changes necessary for complete mod uninstallation
        (including dependencies).

        Keyword arguments:
            mod: The mod to uninstall.

        Returns:
            File changes necessary for successful mod uninstallations.

        Raises:
            NotInstalled: The requested mod is not installed.
            WouldBrokeDependency: Uninstallation of requested mod would
                result in broken dependencies.
        """

        def uniq_names(mods: Iterable[Mod]) -> Generator[Mod, None, None]:
            srt = sorted(mods, key=lambda m: m.name)
            yield from (next(g) for k, g in groupby(srt, key=lambda m: m.name))

        if mod.id not in self.installed:
            raise exceptions.NotInstalled(mod.name)

        # Check for broken dependencies
        broken = [i.mod for i in self.installed.values() if mod.id in i.dependencies]
        if broken:
            raise exceptions.WouldBrokeDependency(mod, uniq_names(broken))

        # Everything seems to be fine, proceed.
        mods_after_removal = dict(self.mods)
        main = mods_after_removal.pop(mod.id, None)
        if main is not None:
            change = [FileChange.removal(self, main)]
        else:
            change = []

        return change + [FileChange.removal(self, o) for o in self.orphans(mods_after_removal)]

    def upgrade_changes(
        self: 'ModPack',
        mod: Mod,
        min_release: Release,
        session: requests.Session
    ) -> Sequence['FileChange']:
        """Generate changes necessary for upgrade of a mod to latest available version.

        Keyword arguments:
            mod: The mod to upgrade.
            min_release: Minimal release to consider for upgrade.
            session: requests.Session to use for fetching file information.

        Returns:
            Sequence of upgrade changes.

        Raises:
            NotInstalled: The requested mod is not installed.
        """

        def appropriate_change(new_file: File) -> FileChange:
            """Determine appropriate change for new file."""

            if new_file.mod.id in self.installed:
                return FileChange.upgrade(self, new_file)
            else:
                return FileChange.installation(self, self.dependencies, new_file)

        if mod.id not in self.installed:
            raise exceptions.NotInstalled

        # Detect all possible upgrades
        files = latest_file_tree(self.game, mod, min_release, session=session)
        files = self.filter_obsoletes(files)
        changes = list(map(appropriate_change, files))

        return changes

    def install(
        self: 'ModPack',
        mod: Mod,
        min_release: Release,
        session: requests.Session
    ) -> None:
        """Install specified mod into the mod-pack.

        Keyword arguments:
            mod: The mod to install.
            min_release: Minimal release type to consider for installation.
            session: Authorized requests.Session to use for fetching
                available file information.

        Raises:
            AlreadyInstalled: The requested mod is already installed.
            NoFilesAvailable: There are no files available for mod-pack's
                version of the game for the specified mod.
        """

        return self.apply(self.install_changes(mod, min_release, session))


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

    @property
    def __valid_source(self):
        """Indicates that source operations may be safely performed."""
        return all(v is not None for v in (self.source, self.old_file))

    @property
    def __valid_destination(self):
        """Indicates that destination operations may be safely performed."""
        return all(v is not None for v in (self.destination, self.new_file))

    @property
    def __file_change(self):
        """Indicate that the file name and/or contents should be changed."""
        return self.new_file != self.old_file

    @property
    def __store_change(self):
        """Indicate that the storage of the file should be changed."""
        return self.destination != self.source

    def __attr_post_init__(self):
        if self.__valid_source or self.__valid_destination:
            return

        if not self.__valid_source:
            raise TypeError('Invalid FileChange: source')
        elif not self.__valid_destination:
            raise TypeError('Invalid FileChange: destination')

    # Creation helpers

    @classmethod
    def installation(
        cls: Type['FileChange'],
        mp: ModPack,
        where: OrderedDict,
        file: File
    ) -> 'FileChange':
        """Create new change for installation.

        Keyword arguments:
            mp: The ModPack to install to.
            where: Where in the ModPack to install (mods or dependencies).
            file: The file to install.

        Returns:
            Installation FileChange.
        """

        return cls(mp, source=None, old_file=None, destination=where, new_file=file)

    @classmethod
    def explicit(
        cls: Type['FileChange'],
        mp: ModPack,
        file: File
    ) -> 'FileChange':
        """Create new change for marking dependency as explicitly installed.

        Keyword arguments:
            mp: Which ModPack to modify.
            file: The dependency to mark as mod.

        Returns:
            Explicit mark FileChange.
        """

        return cls(
            pack=mp,
            source=mp.dependencies, old_file=file,
            destination=mp.mods, new_file=file,
        )

    @classmethod
    def upgrade(
        cls: Type['FileChange'],
        mp: ModPack,
        file: File
    ) -> 'FileChange':
        """Create new change for upgrading a file.

        Keyword arguments:
            mp: Which ModPack to modify.
            file: The new upgrade file.

        Returns:
            Upgrade FileChange.

        Raises:
            KeyError: No older version of the upgrade was found.
        """

        where = next(filter(lambda d: file.mod.id in d, (mp.mods, mp.dependencies)), None)
        if where is None:
            raise KeyError('No old file for upgrade: {file.mod!r}'.format_map(locals()))

        return cls(
            pack=mp,
            source=where, old_file=where[file.mod.id],
            destination=where, new_file=file,
        )

    @classmethod
    def removal(
        cls: Type['FileChange'],
        mp: ModPack,
        file: File
    ) -> 'FileChange':
        """Create a new change for removing a file.

        Keyword arguments:
            mp: Which ModPack to modify.
            file: The file to remove.

        Returns:
            Remove FileChange.

        Raises:
            KeyError: File was not found in ModPack.
        """

        where = next(filter(lambda d: file.mod.id in d, (mp.mods, mp.dependencies)), None)
        if where is None or where[file.mod.id].id != file.id:
            raise KeyError('Removed file not found: {file.id}: {file.name!s}'.format_map(locals()))

        return cls(
            pack=mp,
            source=where, old_file=file,
            destination=None, new_file=None,
        )

    # Path properties

    @property
    def old_path(self):
        """Full path to the old file."""
        if self.__valid_source:
            return self.pack.path / self.old_file.name
        else:
            return None

    @property
    def new_path(self):
        """Full path to the new file."""
        if self.__valid_destination:
            return self.pack.path / self.new_file.name
        else:
            return None

    @property
    def tmp_path(self):
        """Full path to the old file."""
        if self.__valid_source:
            tmp_name = '.'.join([self.old_file.name, 'disabled'])
            return self.pack.path / tmp_name
        else:
            return None

    # Change context

    def __enter__(self: 'FileChange') -> Optional[File]:
        """Prepare storage and file system for potential new file.

        Returns:
            The new file metadata, if there is a file to be manipulated.
        """

        if self.__valid_source:
            if self.__store_change:
                del self.source[self.old_file.mod.id]
            if self.__file_change:
                self.old_path.rename(self.tmp_path)

        if self.__valid_destination and self.__file_change:
            return self.new_file
        else:
            return None

    def __exit__(self: 'FileChange', *exc) -> None:
        """Clean up after change -- both success and failure."""

        if any(exc):  # Failure -- rollback
            if self.__valid_destination:
                if self.__file_change:
                    # Ignore missing file on deletion
                    with suppress(FileNotFoundError):
                        self.new_path.unlink()

            if self.__valid_source:
                if self.__file_change:
                    self.tmp_path.rename(self.old_path)
                if self.__store_change:
                    self.source[self.old_file.mod.id] = self.old_file

        else:  # Success -- change metadata
            if self.__valid_destination:
                self.destination[self.new_file.mod.id] = self.new_file

            # Clean temporary file
            if self.__valid_source and self.__file_change:
                    self.tmp_path.unlink()
