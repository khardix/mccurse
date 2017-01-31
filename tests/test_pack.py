"""Tests for the pack submodule"""

from copy import deepcopy
from io import StringIO
from itertools import repeat
from pprint import pprint

import cerberus
import pytest
from iso8601 import parse_date

from mccurse import pack
from mccurse.addon import Release
from mccurse.curse import Game
from mccurse.util import yaml


@pytest.fixture
def pack_validator() -> cerberus.Validator:
    return cerberus.Validator(cerberus.schema_registry.get('pack'))


@pytest.fixture
def valid_mod_file() -> dict:
    return {
        'id': 42,
        'name': 'test-mod-file.jar',
        'date': parse_date('2017-01-24T18:01+01:00'),
        'release': Release['Beta'],
        'url': 'https://example.com/test-mod-file.jar',
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
        'summary': 'Modify all the tools, then do it again!',
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
