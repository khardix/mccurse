"""Tests for the pack submodule"""

from copy import deepcopy
from datetime import timedelta
from itertools import repeat
from io import StringIO
from pathlib import Path
from typing import Optional

import attr
import betamax
import cerberus
import pytest
import requests
import responses
from pytest import lazy_fixture as lazy

from mccurse import pack, exceptions, proxy
from mccurse.addon import File, Release, Mod
from mccurse.curse import Game
from mccurse.util import yaml


class SimulatedException(Exception):
    """Simulated exception thrown for testing purposes."""


# Fixtures

# # Pack fixtures

@pytest.fixture
def minimal_pack(tmpdir) -> pack.ModPack:
    """Minimal valid mod-pack."""

    return pack.ModPack(game=Game.find('minecraft'), path=Path(str(tmpdir)))


@pytest.fixture
def valid_pack(minecraft, tmpdir, tinkers_construct_file, mantle_file) -> pack.ModPack:
    """Mod-pack with installed files."""

    mp = pack.ModPack(game=minecraft, path=Path(str(tmpdir)))
    mp.mods[tinkers_construct_file.mod.id] = tinkers_construct_file
    mp.dependencies[mantle_file.mod.id] = mantle_file

    return mp


@pytest.fixture
def valid_pack_with_file_contents(valid_pack) -> pack.ModPack:
    """Mod-pack with actual file contents on expected places."""

    mfile = next(iter(valid_pack.mods.values()))
    dfile = next(iter(valid_pack.dependencies.values()))

    mpath, dpath = map(lambda f: valid_pack.path / f.name, (mfile, dfile))

    with mpath.open(mode='wt', encoding='utf-8') as m:
        m.write('MOD:FIXTURE')
    with dpath.open(mode='wt', encoding='utf-8') as d:
        d.write('DEP:FIXTURE')

    return valid_pack


# # FileChange fixtures

@pytest.fixture
def change_install(minimal_pack, tinkers_construct_file) -> pack.FileChange:
    """Change representing installation of a file."""

    return pack.FileChange(
        pack=minimal_pack,
        source=None, old_file=None,
        destination=minimal_pack.mods, new_file=tinkers_construct_file,
    )


@pytest.fixture
def change_explicit(valid_pack_with_file_contents) -> pack.FileChange:
    """Change representing marking file as explicitly installed."""

    file = next(iter(valid_pack_with_file_contents.dependencies.values()))

    return pack.FileChange(
        pack=valid_pack_with_file_contents,
        source=valid_pack_with_file_contents.dependencies, old_file=file,
        destination=valid_pack_with_file_contents.mods, new_file=file,
    )


@pytest.fixture
def change_upgrade(valid_pack_with_file_contents, tinkers_update) -> pack.FileChange:
    """Change representing file upgrade."""

    modpack = valid_pack_with_file_contents
    file = next(iter(modpack.mods.values()))

    return pack.FileChange(
        pack=modpack,
        source=modpack.mods, old_file=file,
        destination=modpack.mods, new_file=tinkers_update,
    )


@pytest.fixture
def change_remove(valid_pack_with_file_contents) -> pack.FileChange:
    """Change representing file removal."""

    modpack = valid_pack_with_file_contents
    file = next(iter(modpack.mods.values()))

    return pack.FileChange(
        pack=modpack,
        source=modpack.mods, old_file=file,
        destination=None, new_file=None,
    )


parametrize_all_changes = pytest.mark.parametrize('change', [
    pytest.lazy_fixture('change_install'),
    pytest.lazy_fixture('change_explicit'),
    pytest.lazy_fixture('change_upgrade'),
    pytest.lazy_fixture('change_remove'),
])


# # YAML fixtures

@pytest.fixture
def yaml_validator() -> cerberus.Validator:
    """Validator for mod-pack data loaded from YAML."""

    return cerberus.Validator(cerberus.schema_registry.get('pack'))


@pytest.fixture
def minimal_yaml(minimal_pack) -> StringIO:
    """Minimal YAML structure for mod-pack."""

    text = """\
        game: !game
            name: {minimal_pack.game.name}
        files:
            path: {minimal_pack.path!s}
    """.format_map(locals())

    return StringIO(text)


@pytest.fixture
def valid_yaml(valid_pack) -> StringIO:
    """Valid YAML mod-pack structure."""

    structure = {
        'game': valid_pack.game,
        'files': {
            'path': str(valid_pack.path),
            'mods': list(valid_pack.mods.values()),
            'dependencies': list(valid_pack.dependencies.values()),
        },
    }

    return StringIO(yaml.dump(structure))


@pytest.fixture
def invalid_yaml(valid_pack) -> StringIO:
    """Invalid YAML mod-pack strucutre: missing path"""

    structure = {
        'game': valid_pack.game,
        'files': {
            'mods': list(valid_pack.mods.values()),
            'dependencies': list(valid_pack.dependencies.values()),
        },
    }

    return StringIO(yaml.dump(structure))


# Tests

# # File changes

@parametrize_all_changes
def test_change_shortcuts(change):
    """Verify the values of shortcut properties."""

    def make_path(root: Path, file: Optional[File], extra_suffix: str = None) -> Optional[Path]:
        if file is None:
            return None
        if extra_suffix is not None:
            name = '.'.join([file.name, extra_suffix])
        else:
            name = file.name

        return root / name

    EXPECT_NEW = make_path(change.pack.path, change.new_file)
    EXPECT_OLD = make_path(change.pack.path, change.old_file)
    EXPECT_TMP = make_path(change.pack.path, change.old_file, 'disabled')

    assert change.new_path == EXPECT_NEW
    assert change.old_path == EXPECT_OLD
    assert change.tmp_path == EXPECT_TMP


def test_change_installation(change_install):
    """Assert proper handling of installation change."""

    EXPECT_CONTENT = 'MOD:INSTALL\n'

    def assert_pre_conditions(mp: pack.ModPack, file: File):
        path = mp.path / file.name
        assert file.mod.id not in mp.mods
        assert not path.exists()

    def assert_post_conditions(mp: pack.ModPack, file: File):
        path = mp.path / file.name
        assert file.mod.id in mp.mods
        assert path.is_file()
        assert path.read_text(encoding='utf-8') == EXPECT_CONTENT

    assert_pre_conditions(change_install.pack, change_install.new_file)

    with pytest.raises(SimulatedException), change_install as nfile:
        assert nfile is not None
        assert change_install.tmp_path is None

        npath = change_install.pack.path / nfile.name
        npath.write_text(EXPECT_CONTENT, encoding='utf-8')
        raise SimulatedException()

    assert_pre_conditions(change_install.pack, change_install.new_file)

    with change_install as nfile:
        assert nfile is not None
        assert change_install.tmp_path is None

        npath = change_install.pack.path / nfile.name
        npath.write_text(EXPECT_CONTENT, encoding='utf-8')

    assert_post_conditions(change_install.pack, change_install.new_file)


def test_change_mark_explicit(change_explicit):
    """Assert handling of explicit mark."""

    EXPECT_CONTENT = change_explicit.old_path.read_text(encoding='utf-8')

    def assert_pre_conditions(mp: pack.ModPack, file: File):
        path = mp.path / file.name
        assert file.mod.id in mp.dependencies
        assert file.mod.id not in mp.mods
        assert path.exists()
        assert path.read_text(encoding='utf-8') == EXPECT_CONTENT

    def assert_post_conditions(mp: pack.ModPack, file: File):
        path = mp.path / file.name
        assert file.mod.id not in mp.dependencies
        assert file.mod.id in mp.mods
        assert path.exists()
        assert path.read_text(encoding='utf-8') == EXPECT_CONTENT

    assert_pre_conditions(change_explicit.pack, change_explicit.old_file)

    with pytest.raises(SimulatedException), change_explicit as nfile:
        assert nfile is None

        raise SimulatedException

    assert_pre_conditions(change_explicit.pack, change_explicit.old_file)

    with change_explicit as nfile:
        assert nfile is None

    assert_post_conditions(change_explicit.pack, change_explicit.new_file)


def test_change_upgrade(change_upgrade):
    """Assert handling of upgrade."""

    EXPECT_OLD_CONTENT = change_upgrade.old_path.read_text(encoding='utf-8')
    EXPECT_NEW_CONTENT = 'MOD:UPGRADE\n'

    def assert_pre_conditions(mp: pack.ModPack, ofile: File, nfile: File):
        opath, npath = map(mp.path.joinpath, (ofile.name, nfile.name))

        assert ofile.mod.id == nfile.mod.id
        assert mp.mods[ofile.mod.id].id == ofile.id
        assert mp.mods[nfile.mod.id].id != nfile.id

        assert opath.exists()
        assert opath.read_text(encoding='utf-8') == EXPECT_OLD_CONTENT
        assert not npath.exists()

    def assert_post_conditions(mp: pack.ModPack, ofile: File, nfile: File):
        opath, npath = map(mp.path.joinpath, (ofile.name, nfile.name))

        assert ofile.mod.id == nfile.mod.id
        assert mp.mods[ofile.mod.id].id != ofile.id
        assert mp.mods[nfile.mod.id].id == nfile.id

        assert not opath.exists()
        assert npath.exists()
        assert npath.read_text(encoding='utf-8') == EXPECT_NEW_CONTENT

    assert_pre_conditions(change_upgrade.pack, change_upgrade.old_file, change_upgrade.new_file)

    with pytest.raises(SimulatedException), change_upgrade as nfile:
        assert nfile is not None
        assert change_upgrade.tmp_path.exists()

        npath = change_upgrade.pack.path / nfile.name
        npath.write_text(EXPECT_NEW_CONTENT, encoding='utf-8')

        raise SimulatedException()

    assert_pre_conditions(change_upgrade.pack, change_upgrade.old_file, change_upgrade.new_file)

    with change_upgrade as nfile:
        assert nfile is not None
        assert change_upgrade.tmp_path.exists()

        npath = change_upgrade.pack.path / nfile.name
        npath.write_text(EXPECT_NEW_CONTENT, encoding='utf-8')

    assert_post_conditions(change_upgrade.pack, change_upgrade.old_file, change_upgrade.new_file)


def test_change_remove(change_remove):
    """Assert handling of removal."""

    EXPECT_CONTENT = change_remove.old_path.read_text(encoding='utf-8')

    def assert_pre_conditions(mp: pack.ModPack, file: File):
        path = mp.path / file.name

        assert file.mod.id in mp.mods
        assert path.exists()
        assert path.read_text(encoding='utf-8') == EXPECT_CONTENT

    def assert_post_conditions(mp: pack.ModPack, file: File):
        path = mp.path / file.name

        assert file.mod.id not in mp.mods
        assert not path.exists()

    assert_params = change_remove.pack, change_remove.old_file

    assert_pre_conditions(*assert_params)

    with pytest.raises(SimulatedException), change_remove as nfile:
        assert nfile is None
        assert change_remove.tmp_path.exists()

        raise SimulatedException()

    assert_pre_conditions(*assert_params)

    with change_remove as nfile:
        assert nfile is None
        assert change_remove.tmp_path.exists()

    assert_post_conditions(*assert_params)


def test_change_helper_installation(change_install, minimal_pack, tinkers_construct_file):
    """Install helper generates expected change."""

    nchange = pack.FileChange.installation(
        minimal_pack,
        where=minimal_pack.mods,
        file=tinkers_construct_file,
    )

    assert nchange == change_install


@pytest.mark.parametrize('helper,change,pack,file', [
    (
        pack.FileChange.explicit,
        lazy('change_explicit'),
        lazy('valid_pack_with_file_contents'),
        lazy('mantle_file'),
    ),
    (
        pack.FileChange.upgrade,
        lazy('change_upgrade'),
        lazy('valid_pack_with_file_contents'),
        lazy('tinkers_update'),
    ),
    (
        pack.FileChange.removal,
        lazy('change_remove'),
        lazy('valid_pack_with_file_contents'),
        lazy('tinkers_construct_file'),
    ),
])
def test_change_creation_helper(helper, change, pack, file):
    """Other helpers generate expected changes."""

    nchange = helper(mp=pack, file=file)
    assert nchange == change


# # YAML validation, loading and dumping

@pytest.mark.parametrize('yaml_stream,expected_status', [
    (pytest.lazy_fixture('minimal_yaml'), True),
    (pytest.lazy_fixture('valid_yaml'), True),
    (pytest.lazy_fixture('invalid_yaml'), False),
])
def test_yaml_schema(yaml_validator, yaml_stream, expected_status):
    """After loading from YAML, the validator correctly validates the structure."""

    document = yaml.load(yaml_stream)
    status = yaml_validator.validate(document)

    # Echo status for debugging
    print('=== Document ===', yaml.dump(yaml_validator.document), sep='\n')
    print('=== Errors ===', yaml.dump(yaml_validator.errors), sep='\n')

    assert status == expected_status


@pytest.mark.parametrize('yaml_stream,expected_pack', [
    tuple(map(pytest.lazy_fixture, ('minimal_yaml', 'minimal_pack'))),
    tuple(map(pytest.lazy_fixture, ('valid_yaml', 'valid_pack'))),
])
def test_modpack_load_success(yaml_stream, expected_pack):
    """Can the "hand-written" representation be loaded?"""

    assert pack.ModPack.load(yaml_stream) == expected_pack


@pytest.mark.parametrize('yaml_stream', [
    pytest.lazy_fixture('invalid_yaml'),
])
def test_modpack_load_failure(yaml_stream):
    """The loading failure is properly reported."""

    with pytest.raises(exceptions.InvalidStream):
        pack.ModPack.load(yaml_stream)


@pytest.mark.parametrize('modpack', [
    pytest.lazy_fixture('minimal_pack'),
    pytest.lazy_fixture('valid_pack'),
])
def test_modpack_roundtrip(modpack):
    """Can the pack be stored and then load again fully?"""

    iostream = StringIO()

    modpack.dump(iostream)
    assert iostream.getvalue()

    iostream.seek(0)
    restored = pack.ModPack.load(iostream)

    assert restored == modpack


def test_modpack_fetch(minimal_pack, tinkers_update):
    """Does the File.fetch fetches the file correctly?"""

    minimal_pack.path /= 'files'
    session = requests.Session()
    file = tinkers_update

    with betamax.Betamax(session).use_cassette('file-fetch'):
        with pytest.raises(OSError):
            minimal_pack.fetch(file, session=session)

        minimal_pack.path.mkdir()
        minimal_pack.fetch(file, session=session)

        filepath = minimal_pack.path / file.name
        assert filepath.is_file()
        assert filepath.stat().st_mtime == file.date.timestamp()

    with responses.RequestsMock() as rsps:
        minimal_pack.fetch(file, session=session)

        assert len(rsps.calls) == 0


def test_modpack_filter_obsoletes(
    valid_pack,
    tinkers_construct_file,
    tinkers_update,
    mantle_file
):
    """Test filtering of obsolete files."""

    older = attr.evolve(mantle_file, date=mantle_file.date-timedelta(hours=1))

    INPUT = [older, tinkers_construct_file, tinkers_update, mantle_file]
    EXPECT = {tinkers_update}

    assert set(valid_pack.filter_obsoletes(INPUT)) == EXPECT


def test_modpack_filter_no_obsoletes(
    minimal_pack, tinkers_construct_file, mantle_file
):
    """Obsolete filtering on empty pack returns exactly the input."""

    INPUT = [tinkers_construct_file, mantle_file]

    assert list(minimal_pack.filter_obsoletes(INPUT)) == INPUT


def test_modpack_orphans(valid_pack, mantle_file):
    """Test if the orphan is found properly"""

    # Prepare orphaned mods
    orphan_parent, orphan_child = map(deepcopy, repeat(mantle_file.mod, 2))
    orphan_child.id += 43
    orphan_parent.id += 42

    # Create orphaned files
    dependency = attr.evolve(mantle_file, mod=orphan_child, name='ORPHAN:CHILD')
    dependent = attr.evolve(
        mantle_file,
        mod=orphan_parent,
        dependencies=mantle_file.dependencies + [orphan_child.id],
        name='ORPHAN:PARENT',
    )

    orphan_files = {dependency, dependent}

    # Add both orphans to the dependencies
    valid_pack.dependencies.update((o.mod.id, o) for o in orphan_files)
    assert set(valid_pack.orphans()) == {dependency, dependent}


def test_modpack_apply(
        minimal_pack,
        minecraft,
        tinkers_construct_file,
        mantle_file,
        tinkers_update
):
    """Test proper application of change sequence."""

    session = requests.Session()

    mp = minimal_pack
    mp.game = minecraft

    with betamax.Betamax(session).use_cassette('modpack-apply'):
        changes_install = [
            pack.FileChange.installation(mp, where=mp.dependencies, file=mantle_file),
            pack.FileChange.installation(mp, where=mp.mods, file=tinkers_construct_file),
        ]
        minimal_pack.apply(changes_install, session=session)

        # Upgrade requires the mod to already exist in the mod-pack
        changes_upgrade = [
            pack.FileChange.explicit(mp, file=mantle_file),
            pack.FileChange.upgrade(mp, file=tinkers_update),
        ]
        minimal_pack.apply(changes_upgrade, session=session)

    assert not minimal_pack.dependencies
    assert len(minimal_pack.mods) == 2
    assert mantle_file.mod.id in minimal_pack.mods
    assert tinkers_update.mod.id in minimal_pack.mods
    assert minimal_pack.mods[tinkers_construct_file.mod.id] == tinkers_update

    mantle_path = mp.path / mantle_file.name
    tinkers_path = mp.path / tinkers_update.name

    assert mantle_path.exists() and tinkers_path.exists()


def test_modpack_install_changes(
    minimal_pack,
    minecraft,
    tinkers_construct,
    available_tinkers_tree
):
    """Test proper installation changes."""

    # Expect change: file mod id, destination
    EXPECT = [
        (74072, minimal_pack.mods),  # Tinkers Construct
        (74924, minimal_pack.dependencies),  # Mantle
    ]

    session = requests.Session()
    minimal_pack.game = minecraft

    with available_tinkers_tree:
        changes = minimal_pack.install_changes(tinkers_construct, Release.Release, session)

    assert len(changes) == 2
    for change, expectation in zip(changes, EXPECT):
        mod_id, target = expectation

        assert change.new_file.mod.id == mod_id
        assert change.destination is target


@responses.activate
def test_modpack_already_installed(
    valid_pack,
    tinkers_construct,
):
    """Test reporting of already installed file."""

    with pytest.raises(exceptions.AlreadyInstalled):
        valid_pack.install_changes(tinkers_construct, Release.Release, requests.Session())


@responses.activate
def test_modpack_install_no_available_file(minimal_pack):
    """Test reporting of no available file."""

    responses.add(
        responses.GET, proxy.HOME_URL + '/addon/12345/files',
        json={'files': []},
    )

    dummy_mod = Mod(id=12345, name='Dummy', summary=str())

    with pytest.raises(exceptions.NoFileFound):
        minimal_pack.install_changes(dummy_mod, Release.Release, requests.Session())


@responses.activate
def test_modpack_remove_changes(
    valid_pack,
    tinkers_construct,
):
    """Test proper uninstallation of a mod with dependency."""

    changes = valid_pack.remove_changes(tinkers_construct)

    assert len(responses.calls) == 0
    assert len(changes) == 2
    assert set(c.old_file.mod.id for c in changes) == {74072, 74924}


@responses.activate
def test_modpack_remove_not_installed(valid_pack):
    """Test proper handling of uninstallation for not installed mod."""

    dummy_mod = Mod(id=12345, name='Dummy', summary=str())

    with pytest.raises(exceptions.NotInstalled):
        valid_pack.remove_changes(dummy_mod)


@responses.activate
def test_modpack_remove_broken_deps(valid_pack, mantle):
    """Test proper detection of broken dependencies."""

    with pytest.raises(exceptions.WouldBrokeDependency):
        valid_pack.remove_changes(mantle)


def test_modpack_upgrade_changes(
    valid_pack,
    tinkers_construct,
    available_tinkers_tree,
):
    """Test proper upgrade of specified mod."""

    with available_tinkers_tree:
        changes = valid_pack.upgrade_changes(
            tinkers_construct,
            Release.Release,
            requests.Session(),
        )

    assert len(changes) == 1
    assert changes[0].new_file.id == 2353329


def test_modpack_install(
    minimal_pack,
    minecraft,
    tinkers_construct,
    available_tinkers_tree
):
    """Test proper installation."""

    session = requests.Session()
    minimal_pack.game = minecraft

    assert not minimal_pack.mods
    assert not minimal_pack.dependencies

    with available_tinkers_tree:
        minimal_pack.install(tinkers_construct, Release.Release, session)

    assert tinkers_construct.id in minimal_pack.mods
    assert minimal_pack.dependencies
