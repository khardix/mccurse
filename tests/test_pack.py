"""Tests for the pack submodule"""

from contextlib import suppress
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path
from typing import Sequence, Tuple

import cerberus
import pytest

from mccurse import pack
from mccurse.addon import Release, File, Mod
from mccurse.curse import Game
from mccurse.pack import resolve
from mccurse.util import yaml


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

    mfile = next(valid_pack.mods.values())
    dfile = next(valid_pack.dependencies.values())

    mpath, dpath = map(lambda f: valid_pack.path / f.name, (mfile, dfile))

    with mpath.open(mode='wt', encoding='utf-8') as m:
        m.write('MOD:FIXTURE')
    with dpath.open(mode='wt', encoding='utf-8') as d:
        d.write('DEP:FIXTURE')

    return valid_pack


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

    with pytest.raises(pack.ValidationError):
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


def test_modpack_replacing_sucessfull(pack_directory):
    """Does the replacing works as expected?"""

    mp, path = pack_directory
    file, = mp.dependencies.values()
    change = pack.FileChange(mp.dependencies, mp.mods, file)

    file_path = path / file.name
    temp_path = path / (file.name + '.disabled')
    contents = file_path.read_text(encoding='utf-8')

    assert file.mod.id in change.old_store
    assert file.mod.id not in change.new_store
    assert file_path.is_file()

    with mp.replacing(change) as nfile:
        assert nfile.mod.id in change.old_store
        assert nfile.mod.id not in change.new_store

        assert not file_path.exists()
        assert temp_path.is_file()

        with (mp.path/nfile.name).open(mode='wt', encoding='utf-8') as stream:
            stream.write('New file\n')

    assert file.mod.id not in change.old_store
    assert file.mod.id in change.new_store
    assert file_path.is_file()
    assert file_path.read_text(encoding='utf-8') != contents
    assert not temp_path.exists()


def test_modpack_replacing_abort(pack_directory):
    """Does the replacing works as expected?"""

    class SimulatedException(Exception):
        pass

    mp, path = pack_directory
    file, = mp.dependencies.values()
    change = pack.FileChange(mp.dependencies, mp.mods, file)

    file_path = path / file.name
    temp_path = path / (file.name + '.disabled')
    contents = file_path.read_text(encoding='utf-8')

    assert file.mod.id in change.old_store
    assert file.mod.id not in change.new_store
    assert file_path.is_file()

    with suppress(SimulatedException), mp.replacing(change) as nfile:
        assert nfile.mod.id in change.old_store
        assert nfile.mod.id not in change.new_store

        assert not file_path.exists()
        assert temp_path.is_file()

        with (mp.path/nfile.name).open(mode='wt', encoding='utf-8') as stream:
            stream.write('New file\n')

        raise SimulatedException()

    assert file.mod.id in change.old_store
    assert file.mod.id not in change.new_store
    assert file_path.is_file()
    assert file_path.read_text(encoding='utf-8') == contents
    assert not temp_path.exists()


def test_filter_obsoletes(filled_modpack, tinkers_construct_file, mantle_file):
    """Does the obsoletes filtering work as expected?"""

    older = deepcopy(tinkers_construct_file)
    older.date = older.date - timedelta(days=1)

    current = deepcopy(mantle_file)

    newer = deepcopy(mantle_file)
    newer.date = newer.date + timedelta(minutes=1)

    results = list(filled_modpack.filter_obsoletes((older, current, newer)))

    assert older not in results
    assert current not in results
    assert newer in results


def test_orphans(filled_modpack, tinkers_construct_file, mantle_file):
    """Orphans listing works as expected?"""

    orphan = deepcopy(mantle_file)
    orphan.mod.id = 123456

    filled_modpack.dependencies[orphan.mod.id] = orphan

    results = list(filled_modpack.orphans())

    assert tinkers_construct_file not in results
    assert mantle_file not in results
    assert orphan in results


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
