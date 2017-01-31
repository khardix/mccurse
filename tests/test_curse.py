"""Tests for the curse submodule."""


import bz2
import datetime
import json
from functools import partial
from pathlib import Path

import betamax
import ijson
import pytest
import requests
import responses
from pyfakefs import fake_filesystem, fake_pathlib

from mccurse import curse
from mccurse.util import yaml


# Fixtures

@pytest.fixture
def minecraft_feed() -> curse.Feed:
    """Feed for testing, with session"""

    return curse.Feed(game_id=432, session=requests.Session())


@pytest.fixture
def game(tmpdir) -> curse.Game:
    """Game pre-initialized with testing objects."""

    # leave session intact
    return curse.Game(
        id=432,  # Minecraft id
        name='Minecraft',
        version='1.10.2',
        cache_dir=Path(str(tmpdir)),
    )


@pytest.fixture
def gamedb() -> Path:
    """Mock supported game database file."""

    file_path = '/gamedb.yaml'
    file_contents = {
        'minecraft': dict(id=432, version='DEFAULT'),
    }

    fs = fake_filesystem.FakeFilesystem(path_separator='/')
    pathlib = fake_pathlib.FakePathlibModule(fs)

    fs.CreateFile(file_path, contents=yaml.dump(file_contents), encoding='utf-8')
    return pathlib.Path(file_path)


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


def test_game_find(gamedb):
    """Is the supported game found correctly?"""

    game = curse.Game.find('minecraft', gamedb=gamedb)

    assert game.id == 432
    assert game.version == 'DEFAULT'

    with pytest.raises(curse.UnsupportedGameError):
        curse.Game.find('unsupported', gamedb=gamedb)


def test_game_yaml(monkeypatch, minecraft, gamedb):
    """Does the YAML serialization work as expected?"""

    EXPECT_YAML = '''
    !game
    name: Minecraft
    version: SELECTED
    '''

    monkeypatch.setattr(curse.Game, 'find', partial(curse.Game.find, gamedb=gamedb))

    roundtrip = yaml.load(yaml.dump(minecraft))
    manual = yaml.load(EXPECT_YAML)

    assert roundtrip == minecraft
    assert manual.id == minecraft.id
    assert manual.version == 'SELECTED'
