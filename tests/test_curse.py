"""Tests for the curse submodule."""


import bz2
import datetime
from pathlib import Path

import betamax
import ijson
import pytest
import requests
import responses
from pyfakefs import fake_filesystem, fake_pathlib

from mccurse import curse


# Fixtures

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


@pytest.fixture
def minecraft_feed() -> curse.Feed:
    """Feed for testing, with session"""

    return curse.Feed(game_id=432, session=requests.Session())


# Feed tests

@responses.activate
def test_complete_feed_url(minecraft_feed):
    """Generate correct feed URL?"""

    EXPECT = '/'.join((
        curse.Feed._BASEURL.format(id=minecraft_feed.game_id),
        curse.Feed._COMPLETE_URL,
    ))

    assert minecraft_feed.complete_url == EXPECT
    assert len(responses.calls) == 0


@responses.activate
def test_complete_timestamp_url(minecraft_feed):
    """Generate correct timestamp URL?"""

    EXPECT = '/'.join((
        curse.Feed._BASEURL.format(id=minecraft_feed.game_id),
        curse.Feed._COMPLETE_URL + '.txt',
    ))

    assert minecraft_feed.complete_timestamp_url == EXPECT
    assert len(responses.calls) == 0


@responses.activate
def test_content_decoding(minecraft_feed):
    """Decode the stream contents correctly?"""

    EXPECT = 'Ahoj světe'
    INPUT = bz2.compress(EXPECT.encode('utf-8'))

    with minecraft_feed._decode_contents(INPUT) as stream:
        decoded = stream.read()

    assert decoded == EXPECT
    assert len(responses.calls) == 0


@responses.activate
def test_timestamp_decoding(minecraft_feed):
    """Decode the timestamp contents correctly?"""

    EXPECT = datetime.datetime(
        year=2012, month=8, day=2,
        hour=12, minute=0, microsecond=123000,
        tzinfo=datetime.timezone.utc,
    )
    # Input is timestamp in microseconds
    INPUT = int(EXPECT.timestamp()*1000)

    assert minecraft_feed._decode_timestamp(INPUT) == EXPECT
    assert len(responses.calls) == 0


def test_fetch_complete_timestamp(minecraft_feed):
    """Fetches and decodes the timestamp correctly?"""

    with betamax.Betamax(minecraft_feed.session).use_cassette('feed-timestamp'):  # noqa: E501
        timestamp = minecraft_feed.fetch_complete_timestamp()
        assert isinstance(timestamp, datetime.datetime)


def test_fetch_complete(minecraft_feed):
    """Fetches and decodes the contents correctly?"""

    with betamax.Betamax(minecraft_feed.session).use_cassette('fetch-feed'), \
            minecraft_feed.fetch_complete() as feed:
        timestamp = next(ijson.items(feed, 'timestamp'), None)
        assert isinstance(timestamp, int)

# Game tests


@responses.activate
def test_default_session(empty_game):
    """Will the game works with no session?"""

    EXPECT = 12345

    responses.add(responses.GET, empty_game.timestamp_url, body=str(EXPECT))

    assert empty_game.current_timestamp() == EXPECT


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
