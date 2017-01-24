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
