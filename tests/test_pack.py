"""Tests for the pack submodule"""

from datetime import datetime

import cerberus
import pytest

from mccurse import pack


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
    return dict(**empty_mod, file=valid_mod_file)


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
        'mods': [valid_mod],
        'dependencies': [],
    }


@pytest.fixture
def invalid_pack(invalid_mod) -> dict:
    return {
        'game': {
            'name': 'Minecraft',
            'version': '1.10.2',
        },
        'mods': [invalid_mod],
        'dependencies': [],
    }


def test_release():
    """Test release creation and ordering"""

    A = pack.Release['Alpha']
    B = pack.Release['Beta']
    R = pack.Release['Release']

    assert A == pack.Release['Alpha']
    assert A < B < R
    assert R > B > A
    assert A != B


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
