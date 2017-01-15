"""Tests for the curse submodule."""


import bz2
import datetime
import json
from pathlib import Path

import betamax
import ijson
import pytest
import requests
import responses

from sqlalchemy.orm.session import Session as SQLSession

from mccurse import curse


# Fixtures

@pytest.fixture
def minecraft_feed() -> curse.Feed:
    """Feed for testing, with session"""

    return curse.Feed(game_id=432, session=requests.Session())


@pytest.fixture
def file_database(tmpdir) -> curse.Database:
    """Database potentially located in temp dir."""

    return curse.Database('test', Path(str(tmpdir)))


@pytest.fixture
def filled_database(file_database) -> curse.Database:
    """Database with some mods filled in."""

    # Create structure
    curse.AddonBase.metadata.create_all(file_database.engine)

    # Add few mods
    session = SQLSession(bind=file_database.engine)
    session.add_all([
        curse.Mod(id=42, name='tested', summary="Mod under test"),
        curse.Mod(id=45, name='tester', summary="Validate tested mod"),
        curse.Mod(id=3, name='unrelated', summary="Dummy"),
    ])
    session.commit()

    return file_database


@pytest.fixture
def game(tmpdir) -> curse.Game:
    """Game pre-initialized with testing objects."""

    # leave session intact
    return curse.Game(
        id=432,  # Minecraft id
        name='Minecraft',
        cache_dir=Path(str(tmpdir)),
    )


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


# Mod tests

def test_json_parsing():
    """Is the mod correctly constructed from JSON data?"""

    INPUT = {
      "Id": 74072,
      "Name": "Tinkers Construct",
      "Summary": "Modify all the things, then do it again!",
    }
    EXPECT = curse.Mod(
        id=74072,
        name="Tinkers Construct",
        summary="Modify all the things, then do it again!",
    )

    assert curse.Mod.from_json(INPUT) == EXPECT


def test_mod_search(filled_database):
    """Does the search return expected results?"""

    EXPECT_IDS = {42, 45}

    session = SQLSession(bind=filled_database.engine)
    selected = curse.Mod.search(session, 'Tested')

    assert {int(m.id) for m in selected} == EXPECT_IDS


def test_mod_find(filled_database):
    """Does the search find the correct mod or report correct error?"""

    session = SQLSession(bind=filled_database.engine)

    assert curse.Mod.find(session, 'Tested').id == 42

    with pytest.raises(curse.MultipleResultsFound):
        curse.Mod.find(session, 'test')

    with pytest.raises(curse.NoResultFound):
        curse.Mod.find(session, 'nonsense')


# Game tests

@responses.activate
def test_gamedata_refresh(game):
    """Does the game refreshes its data correctly?"""

    now = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)  # noqa: E501
    curse_timestamp = int(now.timestamp()*1000)

    # Mock project feed
    mod_path = {'CategorySection': {'Path': 'mods'}}
    other_path = {'CategorySection': {'Path': 'other'}}
    mock_feed_body = {
        'timestamp': curse_timestamp,
        'data': [
            dict(mod_path, Name='test', Id=42, Summary='Test mod'),
            dict(mod_path, Name='nott', Id=15, Summary='No test!'),
            dict(mod_path, Name='tinker', Id=432, Summary='Metamod'),

            dict(other_path, Name='map', Id=16, Summary='Map pack'),
        ]
    }

    # Complete feed
    responses.add(
        responses.GET,
        game.feed.complete_url,
        body=bz2.compress(json.dumps(mock_feed_body).encode('utf-8')),
    )
    # Timestamp
    responses.add(
        responses.GET,
        game.feed.complete_timestamp_url,
        body=str(curse_timestamp).encode('utf-8'),
    )

    game.refresh_data()
    sess = game.database.session()

    assert len(responses.calls) == 2
    assert game.database.version == now
    assert sess.query(curse.Mod).count() == len([
        d for d in mock_feed_body['data']
        if d['CategorySection']['Path'] == 'mods'
    ])


@responses.activate
def test_gamedata_fresh(game):
    """Does the game check the data validity correctly?"""

    data_timestamp = datetime.datetime(
        2017, 1, 15, 0, 0, 0,
        tzinfo=datetime.timezone.utc,
    )
    game.database.version = data_timestamp

    assert game.have_fresh_data(
        valid_period=datetime.timedelta(hours=24),
        now=data_timestamp+datetime.timedelta(hours=12),
    )
    assert not game.have_fresh_data(
        valid_period=datetime.timedelta(hours=24),
        now=data_timestamp+datetime.timedelta(hours=24),
    )
