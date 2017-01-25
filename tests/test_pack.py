"""Tests for the pack submodule"""

from copy import deepcopy
from datetime import datetime
from io import StringIO

import cerberus
import pytest

from mccurse import pack
from mccurse.curse import Game
from mccurse.util import yaml


@pytest.fixture
def pack_validator() -> cerberus.Validator:
    return cerberus.Validator(cerberus.schema_registry.get('pack'))


@pytest.fixture
def valid_mod_file() -> dict:
    return {
        'id': '42',
        'name': 'test-mod-file.jar',
        'date': '2017-01-24T18:01+01:00',
        'release': 'Beta',
    }


@pytest.fixture
def invalid_mod_file() -> dict:
    return {
        'name': 'testfile.zip',
        'date': 'yesterday',
        'release': 'Released',
        'deps': [123, 456],
    }


@pytest.fixture
def empty_mod() -> dict:
    """Empty (without file) mod entry"""
    return {
        'id': 74072,
        'name': 'Tinkers Contruct',
    }


@pytest.fixture
def valid_mod(empty_mod, valid_mod_file) -> dict:
    return dict(**empty_mod, file=deepcopy(valid_mod_file))


@pytest.fixture
def invalid_mod(empty_mod, invalid_mod_file) -> dict:
    return dict(**empty_mod, file=invalid_mod_file)


@pytest.fixture
def minimal_pack() -> dict:
    return {
        'game': {'version': '1.10.2'},
    }


@pytest.fixture
def valid_pack(valid_mod) -> dict:
    return {
        'game': {
            'name': 'Minecraft',
            'version': '1.10.2',
        },
        'mods': [deepcopy(valid_mod)],
        'dependencies': [],
    }


@pytest.fixture
def invalid_pack(invalid_mod) -> dict:
    return {
        'game': {
            'name': 'Minecraft',
            'version': '1.10.2',
        },
        'mods': [deepcopy(invalid_mod)],
        'dependencies': [],
    }


@pytest.fixture
def valid_yaml(valid_pack) -> StringIO:
    stream = StringIO()
    yaml.dump(valid_pack, stream)
    stream.seek(0)

    return stream


@pytest.fixture
def invalid_yaml(invalid_pack) -> StringIO:
    stream = StringIO()
    yaml.dump(invalid_pack, stream)
    stream.seek(0)

    return stream


def test_release():
    """Test release creation and ordering"""

    A = pack.Release['Alpha']
    B = pack.Release['Beta']
    R = pack.Release['Release']

    assert A == pack.Release['Alpha']
    assert A < B < R
    assert R > B > A
    assert A != B


def test_release_and_yaml():
    """Serialization of Release to YAML works as intended?"""

    data = [pack.Release['Alpha']]
    text = '- Alpha\n'

    assert yaml.dump(data) == text
    assert yaml.load(text) == data


def test_mod_file_schema(valid_mod_file, invalid_mod_file):
    """Mod file schema bahving as expected?"""

    schema = cerberus.schema_registry.get('mod-file')
    vld = cerberus.Validator(schema)
    inv = cerberus.Validator(schema)

    assert vld.validate(valid_mod_file)
    assert isinstance(vld.document['id'], int)
    date = vld.document['date']
    assert isinstance(date, datetime) and date.tzinfo is not None
    assert isinstance(vld.document['release'], pack.Release)

    assert not inv.validate(invalid_mod_file)
    assert inv.errors


def test_mod_schema(valid_mod, invalid_mod):
    """Mod schema behaving as expected?"""

    schema = cerberus.schema_registry.get('mod')
    vld = cerberus.Validator(schema)
    inv = cerberus.Validator(schema)

    assert vld.validate(valid_mod)
    assert isinstance(vld.document['id'], int)
    assert isinstance(vld.document['file']['id'], int)

    assert not inv.validate(invalid_mod)


def test_pack_schema(minimal_pack, valid_pack, invalid_pack):
    """Pack schema behaving as expected?"""

    schema = cerberus.schema_registry.get('pack')
    minimal, valid, invalid = map(cerberus.Validator, [schema]*3)

    assert minimal.validate(minimal_pack)
    assert valid.validate(valid_pack)
    assert not invalid.validate(invalid_pack)


def test_modpack_init(valid_pack, invalid_pack):
    """ModPack.__init__ behaves as described?"""

    mp = pack.ModPack(valid_pack)
    assert mp.data

    with pytest.raises(pack.ValidationError):
        mp = pack.ModPack(invalid_pack)


def test_modpack_create():
    """Does ModPack.create work as expected?"""

    gm = Game(id=42, name='Test', version='dev')
    mp = pack.ModPack.create(gm)

    assert mp.data['game']['name'] == gm.name
    assert mp.data['game']['version'] == gm.version


def test_modpack_load(pack_validator, valid_yaml, valid_pack, invalid_yaml):
    """Loading from stream works as advertised?"""

    mp = pack.ModPack.from_yaml(valid_yaml)
    assert mp.data == pack_validator.normalized(valid_pack)

    with pytest.raises(pack.ValidationError):
        mp = pack.ModPack.from_yaml(invalid_yaml)


def test_modpack_dump(pack_validator, valid_pack):
    """Dumping to stream works as advertised?"""

    stream = StringIO()
    mp = pack.ModPack(valid_pack)
    expect = pack_validator.normalized(deepcopy(valid_pack))

    mp.to_yaml(stream)
    print(stream.getvalue())
    data = yaml.load(stream.getvalue())

    assert data == expect
