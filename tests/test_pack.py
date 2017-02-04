"""Tests for the pack submodule"""

from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
from itertools import repeat
from pathlib import Path
from pprint import pprint
from typing import Sequence, Tuple

import cerberus
import pytest

from mccurse import pack
from mccurse.addon import Release, File, Mod
from mccurse.curse import Game
from mccurse.pack import resolve
from mccurse.util import yaml


@pytest.fixture
def pack_validator() -> cerberus.Validator:
    return cerberus.Validator(cerberus.schema_registry.get('pack'))


@pytest.fixture
def minimal_pack(minecraft) -> dict:
    return {
        'game': minecraft,
        'files': {'path': 'mods'}
    }


@pytest.fixture
def valid_pack(minecraft, tinkers_construct_file) -> dict:
    return {
        'game': minecraft,
        'files': {
            'path': 'mods',
            'mods': [tinkers_construct_file],
            'dependencies': [],
        },
    }


@pytest.fixture
def invalid_pack(minecraft, tinkers_construct_file) -> dict:
    return {
        'game': minecraft,
        'files': {
            'mods': [tinkers_construct_file],
            'dependencies': [],
        }
    }


@pytest.fixture
def minimal_yaml(minecraft) -> StringIO:
    text = """\
        game: !game
            name: {minecraft.name}
        files:
            path: mods
    """.format_map(locals())

    return StringIO(text)


@pytest.fixture
def valid_yaml(minecraft, valid_pack) -> StringIO:
    struct = deepcopy(valid_pack)
    return StringIO(yaml.dump(struct))


# Dependency fixtures and helpers

def makefile(name, mod_id, *deps):
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


@pytest.fixture
def pack_directory(tmpdir, minimal_yaml, tinkers_construct_file) -> Tuple[pack.ModPack, Path]:
    """Mod pack with existing files in file system."""

    mp = pack.ModPack.load(minimal_yaml)
    mp.path = Path(str(tmpdir))

    filepath = mp.path / tinkers_construct_file.name
    with filepath.open(mode='wt', encoding='utf-8') as file:
        print('Tinkers Construct Dummy Old File', file=file)
    mp.dependencies[tinkers_construct_file.mod.id] = tinkers_construct_file

    return mp, mp.path


def test_pack_schema(minimal_pack, valid_pack, invalid_pack):
    """Pack schema behaving as expected?"""

    schema = cerberus.schema_registry.get('pack')
    validators = map(cerberus.Validator, repeat(schema))
    operands = zip(
        ('minimal', 'valid', 'invalid'),
        validators,
        (minimal_pack, valid_pack, invalid_pack),
    )
    result = {
        name: {'status': vld.validate(pack), 'doc': vld.document, 'err': vld.errors}
        for name, vld, pack in operands
    }

    pprint(result)

    assert result['minimal']['status'] == True
    assert result['valid']['status'] == True
    assert result['invalid']['status'] == False


def test_modpack_load(minecraft, minimal_yaml, valid_yaml):
    """Can the "hand-written" representation be loaded?"""

    minimal = pack.ModPack.load(minimal_yaml)
    valid = pack.ModPack.load(valid_yaml)

    assert minimal.game == Game.find('minecraft')
    assert len(minimal.mods) == 0

    assert valid.game == minecraft
    assert len(valid.mods) != 0


def test_modpack_dump(valid_yaml):
    """Can the pack be stored and then load again fully?"""

    original = pack.ModPack.load(valid_yaml)
    iostream = StringIO()

    original.dump(iostream)
    assert iostream.getvalue()

    iostream.seek(0)
    restored = pack.ModPack.load(iostream)

    assert restored == original


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


# Resolve tests

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
