"""Tests for addon submodule."""

from datetime import datetime, timezone

import pytest
import responses
from sqlalchemy.orm.session import Session as SQLSession

from mccurse import addon, curse
from mccurse.util import yaml


# Fixtures

@pytest.fixture
def filled_database(file_database) -> curse.Database:
    """Database with some mods filled in."""

    # Create structure
    addon.AddonBase.metadata.create_all(file_database.engine)

    # Add few mods
    session = SQLSession(bind=file_database.engine)
    session.add_all([
        addon.Mod(id=42, name='tested', summary="Mod under test"),
        addon.Mod(id=45, name='tester', summary="Validate tested mod"),
        addon.Mod(id=3, name='unrelated', summary="Dummy"),
    ])
    session.commit()

    return file_database


@pytest.fixture
def date() -> datetime:
    """Timezone-aware datetime."""

    return datetime(year=2017, month=1, day=1, minute=42, tzinfo=timezone.utc)


# Mod tests

def test_json_parsing():
    """Is the mod correctly constructed from JSON data?"""

    INPUT = {
        "Id": 74072,
        "Name": "Tinkers Construct",
        "Summary": "Modify all the things, then do it again!",
    }
    EXPECT = addon.Mod(
        id=74072,
        name="Tinkers Construct",
        summary="Modify all the things, then do it again!",
    )

    assert addon.Mod.from_json(INPUT) == EXPECT


def test_mod_search(filled_database):
    """Does the search return expected results?"""

    EXPECT_IDS = {42, 45}

    session = SQLSession(bind=filled_database.engine)
    selected = addon.Mod.search(session, 'Tested')

    assert {int(m.id) for m in selected} == EXPECT_IDS


def test_mod_find(filled_database):
    """Does the search find the correct mod or report correct error?"""

    session = SQLSession(bind=filled_database.engine)

    assert addon.Mod.find(session, 'Tested').id == 42

    with pytest.raises(addon.NoResultFound):
        addon.Mod.find(session, 'nonsense')


def test_mod_with_id(filled_database):
    """Does the with_id find the correct mod?"""

    session = SQLSession(bind=filled_database.engine)

    assert addon.Mod.with_id(session, 42).name == 'tested'
    assert addon.Mod.with_id(session, 45).name == 'tester'

    with pytest.raises(addon.NoResultFound):
        addon.Mod.with_id(session, 44)


# Release tests

def test_release():
    """Test release creation and ordering"""

    A = addon.Release['Alpha']
    B = addon.Release['Beta']
    R = addon.Release['Release']

    assert A == addon.Release['Alpha']
    assert A < B < R
    assert R > B > A
    assert A != B


def test_release_and_yaml():
    """Serialization of Release to YAML works as intended?"""

    data = [addon.Release['Alpha']]
    text = '- Alpha\n'

    assert yaml.dump(data) == text
    assert yaml.load(text) == data


# File tests

@responses.activate
def test_file_init():
    """Does the File initialization behaves as expected?"""

    m = addon.Mod(id=42, name=str(), summary=str())

    addon.File(
        id=42, mod=m,
        name='test.jar', date=datetime.now(tz=timezone.utc),
        release=addon.Release.Release, url='https://httpbin.org',
    )
    addon.File(
        id=43, mod=m,
        name='test.jar', date=datetime.now(tz=timezone.utc),
        release=addon.Release.Alpha, url='https://httpbin.org',
    )

    with pytest.raises(TypeError):
        addon.File(
            id='43', mod=m,
            name='test.jar', date=datetime.now(tz=timezone.utc),
            release=addon.Release.Beta, url=None,
        )

    assert len(responses.calls) == 0


def test_file_from_proxy(date: datetime):
    """Does the File read the data from RestProxy correctly?"""

    valid_data = {
        'dependencies': [],
        'download_url': 'https://example.org',
        'file_date': date.isoformat(),
        'file_name_on_disk': 'example.jar',
        'id': 42,
        'release_type': 'Release',
    }
    mod = addon.Mod(id=42, name='Test mod', summary='Test')

    a = addon.File.from_proxy(mod, valid_data)

    assert a.id == a.mod.id == 42
    assert a.date == date
    assert a.release == addon.Release.Release


def test_file_yaml(date: datetime):
    """Does the dumping and loading of File to/from YAML works?"""

    EXPECT_FILE = addon.File(
        id=42,
        mod=addon.Mod(id=42, name='Test mod', summary='Testing'),
        name='test.jar',
        date=date,
        release=addon.Release['Beta'],
        url='https://example.com/test.jar',
        dependencies=[],
    )
    EXPECT_YAML = """
        !modfile
        file:
            date: 2017-01-01T00:42:00+00:00
            dependencies: []
            id: 42
            name: test.jar
            release: Beta
            url: https://example.com/test.jar
        id: 42
        name: Test mod
        summary: Testing
    """

    assert yaml.load(yaml.dump(EXPECT_FILE)) == EXPECT_FILE
    assert yaml.load(EXPECT_YAML) == EXPECT_FILE
