"""Tests for the proxy submodule"""

from io import StringIO

import attr
import pytest
import requests
import responses

from mccurse import proxy
from mccurse.util import yaml


# Fixtures

@pytest.fixture
def dummy_auth() -> proxy.Authorization:
    return proxy.Authorization(
        user_id=42,
        token='token',
    )


# Authorization tests

@responses.activate
def test_modified_request(dummy_auth):
    """Is the request properly modified?"""

    # Expected header
    EXPECT = 'Token {}:{}'.format(dummy_auth.user_id, dummy_auth.token)

    url = 'https://example.com'

    responses.add(responses.GET, url, json=[])

    requests.get(url, auth=dummy_auth)

    assert len(responses.calls) == 1

    request = responses.calls[0].request
    assert request.headers['Authorization'] == EXPECT


@responses.activate
def test_authorization_login(dummy_auth):
    """Is the authorization properly constructed from the proxy response?"""

    EXPECT = dummy_auth

    url = '/'.join((proxy.HOME_URL, 'authenticate'))
    responses.add(responses.POST, url, json={
        'session': {
            'user_id': EXPECT.user_id,
            'token': EXPECT.token,
        },
    })

    auth = proxy.Authorization.login('user', 'pass')

    assert EXPECT == auth


def test_auth_loading(dummy_auth):
    """Is the authentication properly loaded from file?"""

    correct = StringIO(yaml.dump(attr.asdict(dummy_auth)))
    empty = StringIO()

    assert proxy.Authorization.load(correct) == dummy_auth

    with pytest.raises(ValueError):
        proxy.Authorization.load(empty)


def test_auth_store(dummy_auth):
    """Is the authentication properly stored into a file?"""

    buffer = StringIO()
    dummy_auth.dump(buffer)

    data = yaml.load(buffer.getvalue())

    assert data == attr.asdict(dummy_auth)
