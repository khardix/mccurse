"""Tests for the curse submodule."""


from pathlib import Path

import attr
import betamax
import pytest
import requests
import responses
from pyfakefs import fake_filesystem, fake_pathlib

from mccurse import curse


@pytest.fixture
def empty_game() -> curse.Game:
    """Dummy game for testing, without session"""

    return curse.Game(id=1, abbr='dm', name='dummy')


@pytest.fixture
def minecraft() -> curse.Game:
    """Dummy game for testing, with session"""

    return curse.Game(
        id=432,
        abbr='mc',
        name='Minecraft',
        session=requests.Session(),
    )


@responses.activate
def test_feed_url(empty_game):
    """Generate correct feed URL?"""

    EXPECT = curse.FEED_URL.format_map(attr.asdict(empty_game))

    assert empty_game.feed_url == EXPECT
    assert len(responses.calls) == 0


@responses.activate
def test_timestamp_url(empty_game):
    """Generate correct timestamp URL?"""

    EXPECT = curse.TIMESTAMP_URL.format_map(attr.asdict(empty_game))

    assert empty_game.timestamp_url == EXPECT
    assert len(responses.calls) == 0


@responses.activate
def test_default_session(empty_game):
    """Will the game works with no session?"""

    EXPECT = 12345

    responses.add(responses.GET, empty_game.timestamp_url, body=str(EXPECT))

    assert empty_game.current_timestamp() == EXPECT


def test_current_timestamp(minecraft):
    """Will the timestamp be fetched correctly?"""

    with betamax.Betamax(minecraft.session).use_cassette('current-timestamp'):
        assert isinstance(minecraft.current_timestamp(), int)


@responses.activate
def test_db_uri_existing(minecraft):
    """Does the game produce expected DB URI?"""

    timestamp = 12345
    parts = {
        'scheme': curse.DB_PROTO,
        'path': Path('/tmp'),
        'dbname': curse.DB_BASENAME.format(
            timestamp=timestamp,
            abbr=minecraft.abbr,
        ),
    }

    EXPECT = '{scheme}/{path}/{dbname}'.format_map(parts)
    RESULT = minecraft.db_uri(target_dir=parts['path'], timestamp=timestamp)

    assert RESULT == EXPECT
    assert len(responses.calls) == 0


def test_db_uri_current(minecraft):
    """Does the game fetch missing timestamp?"""

    with betamax.Betamax(minecraft.session).use_cassette('current-db-uri'):
        parts = {
            'scheme': curse.DB_PROTO,
            'path': Path('/tmp'),
            'dbname': curse.DB_BASENAME.format(
                timestamp=minecraft.current_timestamp(),
                abbr=minecraft.abbr,
            ),
        }

        EXPECT = '{scheme}/{path}/{dbname}'.format_map(parts)
        RESULT = minecraft.db_uri(target_dir=parts['path'])

        assert RESULT == EXPECT


@responses.activate
def test_db_glob_empty(monkeypatch, minecraft):
    """Report no existing databases correctly?"""

    TESTDIR = '/test'

    fs = fake_filesystem.FakeFilesystem()
    fs.CreateDirectory(TESTDIR)
    flib = fake_pathlib.FakePathlibModule(fs)

    it = minecraft.db_glob(flib.Path(TESTDIR))
    assert len(list(it)) == 0
    assert len(responses.calls) == 0


@responses.activate
def test_db_glob_len(monkeypatch, minecraft):
    """Report all existing databases?"""

    TESTDIR = '/test'
    TIMESTAMPS = 42, 43, 44

    fs = fake_filesystem.FakeFilesystem()
    fs.CreateDirectory(TESTDIR)

    for fake_timestamp in TIMESTAMPS:
        filename = '/'.join((
            TESTDIR,
            curse.DB_BASENAME.format(
                abbr=minecraft.abbr,
                timestamp=fake_timestamp,
            ),
        ))
        fs.CreateFile(filename)

    flib = fake_pathlib.FakePathlibModule(fs)

    it = minecraft.db_glob(flib.Path(TESTDIR))
    assert len(list(it)) == len(TIMESTAMPS)
    assert len(responses.calls) == 0
