"""Tests for the curse submodule."""


import attr
import betamax
import pytest
import requests
import responses

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

    with betamax.Betamax(minecraft.session).use_cassette('fetch-timestamp'):
        assert isinstance(minecraft.current_timestamp(), int)
