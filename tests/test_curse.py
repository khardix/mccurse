"""Tests for the curse submodule."""


import bz2
import datetime
from pathlib import Path

import betamax
import ijson
import pytest
import requests
import responses

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


@pytest.fixture
def file_database(tmpdir) -> curse.Database:
    """Database potentially located in temp dir."""

    return curse.Database('test', Path(str(tmpdir)))


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


# Database tests

def test_file_uri(file_database):
    """Construct filesystem URI correctly?"""

    EXPECT = '{scheme}/{path!s}/{name}'.format(
        scheme=curse.Database._SCHEME,
        path=file_database.root_dir.resolve(),
        name=curse.Database._BASENAME.format(
            game_name=file_database.game_name
        ),
    )

    assert file_database.uri == EXPECT


def test_engine_creation(file_database):
    """Is the DB engine created correctly in both types of DB?"""

    QUERY = 'SELECT 1+1'
    EXPECT = (2,)

    assert file_database.engine.execute(QUERY).first() == EXPECT


def test_database_versioning(file_database):
    """Is the data version persisted correctly?"""

    INPUT = datetime.datetime(2012, 12, 12, tzinfo=datetime.timezone.utc)
    timestamp = int(INPUT.timestamp())

    file_database.version = INPUT

    dbstamp, = file_database.engine.execute('PRAGMA user_version').first()

    assert dbstamp == timestamp
    assert file_database.version == INPUT
