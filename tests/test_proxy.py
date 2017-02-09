"""Tests for the proxy submodule"""

from datetime import datetime, timezone
from io import StringIO
from typing import Sequence, Tuple

import attr
import pytest
import requests
import responses

from mccurse import addon, proxy, exceptions
from mccurse.addon import File, Mod, Release
from mccurse.util import yaml


# Fixtures

@pytest.fixture
def dummy_auth() -> proxy.Authorization:
    return proxy.Authorization(
        user_id=42,
        token='token',
    )


# # Dependency fixtures and helpers

def makefile(name: str, mod_id: int, *deps: Sequence[int]):
    """Shortcut for creating instances of File."""

    TIMESTAMP = datetime.now(tz=timezone.utc)
    RELEASE = Release.Release

    return File(
        mod=Mod(name=name.upper(), id=mod_id, summary=name),
        id=(42 + mod_id),
        name='{}.jar'.format(name),
        date=TIMESTAMP,
        release=RELEASE,
        url='http://example.com/{}.jar'.format(name),
        dependencies=list(deps),
    )


@pytest.fixture
def multiple_dependency() -> Tuple[File, dict, Sequence]:
    """Dependency graph with shared dependencies."""

    root = makefile('a', 1, 2, 3)
    deps = {
        1: root,
        2: makefile('b', 2, 3, 4),
        3: makefile('c', 3),
        4: makefile('d', 4, 3),
        # Extra available, should not be included
        5: makefile('e', 5, 3),
    }
    order = [1, 2, 3, 4]

    return root, deps, order


@pytest.fixture
def circular_dependency() -> Tuple[File, dict, Sequence]:
    """Dependency graph with a circle."""

    root = makefile('a', 1, 2)
    deps = {
        1: root,
        2: makefile('b', 2, 3),
        3: makefile('c', 3, 1),
    }
    order = [1, 2, 3]

    return root, deps, order


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

    with pytest.raises(exceptions.InvalidStream):
        proxy.Authorization.load(empty)


def test_auth_store(dummy_auth):
    """Is the authentication properly stored into a file?"""

    buffer = StringIO()
    dummy_auth.dump(buffer)

    data = yaml.load(buffer.getvalue())

    assert data == attr.asdict(dummy_auth)


# Function tests

# # Dependency resolution tests

def test_resolve_multiple(multiple_dependency):
    """Resolving works right with shared dependencies?"""

    root, pool, EXPECT_ORDER = multiple_dependency

    resolution = proxy.resolve(root, pool)

    assert len(resolution) == len(EXPECT_ORDER)
    assert list(resolution.keys()) == EXPECT_ORDER
    assert root.mod.id == next(iter(resolution.values())).mod.id

    required = set(root.dependencies)
    for d in resolution.values():
        required.update(d.dependencies)

    assert all(d in resolution for d in required)


def test_resolve_cycle(circular_dependency):
    """Resolving works right with circular dependencies?"""

    root, pool, EXPECT_ORDER = circular_dependency

    resolution = proxy.resolve(root, pool)

    assert len(resolution) == len(EXPECT_ORDER)
    assert list(resolution.keys()) == EXPECT_ORDER
    assert root.mod.id == next(iter(resolution.values())).mod.id

    required = set(root.dependencies)
    for d in resolution.values():
        required.update(d.dependencies)

    assert all(d in resolution for d in required)


# # Latest function tests

@responses.activate
def test_latest_files(minecraft, tinkers_construct, available_files):
    """Does the latest function pick the right files?"""

    url = proxy.HOME_URL + '/addon/{tinkers_construct.id}/files'.format_map(locals())
    responses.add(responses.GET, url, json=available_files)
    common_args = minecraft, tinkers_construct

    assert proxy.latest(*common_args, addon.Release.Release).id == 2353329
    assert proxy.latest(*common_args, addon.Release.Beta).id == 2366245
    assert proxy.latest(*common_args, addon.Release.Alpha).id == 2366245


@responses.activate
def test_latest_errors(minecraft, tinkers_construct):
    """Does the latest function react correctly on HTTPError?"""

    url = proxy.HOME_URL + '/addon/{tinkers_construct.id}/files'.format_map(locals())
    responses.add(responses.GET, url, status=404)

    with pytest.raises(requests.HTTPError):
        proxy.latest(minecraft, tinkers_construct, addon.Release.Release)


def test_latest_tree(minecraft, tinkers_construct, available_tinkers_tree):
    """Does the tree resolution works as expected?"""

    with available_tinkers_tree as rsps:
        resolution = proxy.latest_file_tree(minecraft, tinkers_construct, addon.Release.Release)

        assert len(rsps.calls) == 2
        assert len(resolution) == 2
        assert set(f.id for f in resolution) == {2366244, 2353329}
        assert next(iter(resolution)).mod.id == tinkers_construct.id
