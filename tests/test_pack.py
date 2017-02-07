"""Tests for the pack submodule"""

from copy import deepcopy
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path
from typing import Sequence, Tuple, Optional

import betamax
import cerberus
import pytest
import requests
import responses

from mccurse import pack, exceptions
from mccurse.addon import Release, File, Mod
from mccurse.curse import Game
from mccurse.pack import resolve
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
def tinkers_update(tinkers_construct_file) -> File:
    """Updated file for tinkers construct."""

    update = deepcopy(tinkers_construct_file)
    update.id += 1
    update.name = 'NEW-' + update.name
    update.date += timedelta(days=1)

    return update


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


# # Dependency fixtures and helpers

def makefile(name: str, mod_id: int, *deps: Sequence[int]):
    """Shortcut for creating instances of File."""

    TIMESTAMP = datetime.now(tz=timezone.utc)
    RELEASE = Release.Release

    return File(
        mod=Mod(name=name.upper(), id=mod_id, summary=name),
        id=(42 + mod_id),
        name='{}.jar'.format(name),
        date=TIMESTAMP,
        release=RELEASE,
        url='http://example.com/{}.jar'.format(name),
        dependencies=list(deps),
    )


@pytest.fixture
def multiple_dependency() -> Tuple[File, dict, Sequence]:
    """Dependency graph with shared dependencies."""

    root = makefile('a', 1, 2, 3)
    deps = {
        1: root,
        2: makefile('b', 2, 3, 4),
        3: makefile('c', 3),
        4: makefile('d', 4, 3),
        # Extra available, should not be included
        5: makefile('e', 5, 3),
    }
    order = [1, 2, 3, 4]

    return root, deps, order


@pytest.fixture
def circular_dependency() -> Tuple[File, dict, Sequence]:
    """Dependency graph with a circle."""

    root = makefile('a', 1, 2)
    deps = {
        1: root,
        2: makefile('b', 2, 3),
        3: makefile('c', 3, 1),
    }
    order = [1, 2, 3]

    return root, deps, order


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


def test_modpack_fetch(minimal_pack, tinkers_construct_file):
    """Does the File.fetch fetches the file correctly?"""

    minimal_pack.path /= 'files'
    session = requests.Session()
    file = tinkers_construct_file

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


# # Dependency resolution tests

def test_resolve_multiple(multiple_dependency):
    """Resolving works right with shared dependencies?"""

    root, pool, EXPECT_ORDER = multiple_dependency

    resolution = resolve(root, pool)

    assert len(resolution) == len(EXPECT_ORDER)
    assert list(resolution.keys()) == EXPECT_ORDER

    required = set(root.dependencies)
    for d in resolution.values():
        required.update(d.dependencies)

    assert all(d in resolution for d in required)


def test_resolve_cycle(circular_dependency):
    """Resolving works right with circular dependencies?"""

    root, pool, EXPECT_ORDER = circular_dependency

    resolution = resolve(root, pool)

    assert len(resolution) == len(EXPECT_ORDER)
    assert list(resolution.keys()) == EXPECT_ORDER

    required = set(root.dependencies)
    for d in resolution.values():
        required.update(d.dependencies)

    assert all(d in resolution for d in required)
