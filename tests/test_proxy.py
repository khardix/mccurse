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


@pytest.fixture
def available_files() -> dict:
    """Test set of available files.

    Ordered by date ascending: 2349845[A], 2353329[R], 2366245[B]
    """

    jsn = {"files": [
        {
            "alternate_file_id": 0,
            "file_name": "TConstruct-1.10.2-2.6.1.jar",
            "is_available": True,
            "dependencies": [
                {
                    "add_on_id": 74924,
                    "type": "Required"
                }
            ],
            "file_date": "2016-12-07T18:35:45",
            "file_status": "SemiNormal",
            "file_name_on_disk": "TConstruct-1.10.2-2.6.1.jar",
            "id": 2353329,
            "download_url":
                "https://addons.cursecdn.com/files/2353/329/TConstruct-1.10.2-2.6.1.jar",
            "package_fingerprint": 1768070072,
            "is_alternate": False,
            "release_type": "Release",
            "game_version": [
                "1.10.2"
            ]
        },
        {
            "alternate_file_id": 0,
            "file_name": "TConstruct-1.10.2-2.6.2.jar",
            "is_available": True,
            "dependencies": [
                {
                    "add_on_id": 74924,
                    "type": "Required"
                }
            ],
            "file_date": "2017-01-09T19:41:50",
            "file_status": "SemiNormal",
            "file_name_on_disk": "TConstruct-1.10.2-2.6.2.jar",
            "id": 2366245,
            "download_url":
                "https://addons.cursecdn.com/files/2366/245/TConstruct-1.10.2-2.6.2.jar",
            "package_fingerprint": 1770865161,
            "is_alternate": False,
            "release_type": "Beta",
            "game_version": [
                "1.10.2"
            ]
        },
        {
            "alternate_file_id": 0,
            "file_name": "TConstruct-1.10.2-2.6.0.jar",
            "is_available": True,
            "dependencies": [
                {
                    "add_on_id": 74924,
                    "type": "Required"
                }
            ],
            "file_date": "2016-11-27T16:25:15",
            "file_status": "SemiNormal",
            "file_name_on_disk": "TConstruct-1.10.2-2.6.0.jar",
            "id": 2349845,
            "download_url":
                "https://addons.cursecdn.com/files/2349/845/TConstruct-1.10.2-2.6.0.jar",
            "package_fingerprint": 1097160304,
            "is_alternate": False,
            "release_type": "Alpha",
            "game_version": [
                "1.10.2"
            ]
        },
    ]}

    return jsn


@pytest.fixture
def available_tinkers_tree(tinkers_construct, mantle_file) -> dict:
    """JSON for tree resolution."""

    pool = {
        proxy.HOME_URL + '/addon/{tinkers_construct.id}/files'.format_map(locals()): {
            'files': [
                {
                    "release_type": "Release",
                    "file_status": "SemiNormal",
                    "game_version": [
                        "1.10.2"
                    ],
                    "file_name_on_disk": "TConstruct-1.10.2-2.6.1.jar",
                    "file_date": "2016-12-07T18:35:45",
                    "download_url":
                        "https://addons.cursecdn.com/files/2353/329/TConstruct-1.10.2-2.6.1.jar",
                    "alternate_file_id": 0,
                    "id": 2353329,
                    "package_fingerprint": 1768070072,
                    "is_available": True,
                    "file_name": "TConstruct-1.10.2-2.6.1.jar",
                    "is_alternate": False,
                    "dependencies": [
                        {
                            "type": "Required",
                            "add_on_id": 74924
                        }
                    ]
                },
                {
                    "release_type": "Beta",
                    "file_status": "SemiNormal",
                    "game_version": [
                        "1.10.2"
                    ],
                    "file_name_on_disk": "TConstruct-1.10.2-2.6.2.jar",
                    "file_date": "2017-01-09T19:41:50",
                    "download_url":
                        "https://addons.cursecdn.com/files/2366/245/TConstruct-1.10.2-2.6.2.jar",
                    "alternate_file_id": 0,
                    "id": 2366245,
                    "package_fingerprint": 1770865161,
                    "is_available": True,
                    "file_name": "TConstruct-1.10.2-2.6.2.jar",
                    "is_alternate": False,
                    "dependencies": [
                        {
                            "type": "Required",
                            "add_on_id": 74924
                        }
                    ]
                },
            ]
        },
        proxy.HOME_URL + '/addon/{mantle_file.mod.id}/files'.format_map(locals()): {
            'files': [
                {
                    "release_type": "Release",
                    "file_status": "SemiNormal",
                    "game_version": [
                        "1.10.2"
                    ],
                    "file_name_on_disk": "Mantle-1.10.2-1.1.4.jar",
                    "file_date": "2017-01-09T19:40:41",
                    "download_url":
                        "https://addons.cursecdn.com/files/2366/244/Mantle-1.10.2-1.1.4.jar",
                    "alternate_file_id": 0,
                    "id": 2366244,
                    "package_fingerprint": 4219802267,
                    "is_available": True,
                    "file_name": "Mantle-1.10.2-1.1.4.jar",
                    "is_alternate": False,
                    "dependencies": []
                },
                {
                    "release_type": "Beta",
                    "file_status": "SemiNormal",
                    "game_version": [
                        "1.9"
                    ],
                    "file_name_on_disk": "Mantle-1.9-0.10.1.jar",
                    "file_date": "2016-05-26T15:37:09",
                    "download_url":
                        "https://addons.cursecdn.com/files/2302/982/Mantle-1.9-0.10.1.jar",
                    "alternate_file_id": 0,
                    "id": 2302982,
                    "package_fingerprint": 3396617729,
                    "is_available": True,
                    "file_name": "Mantle-1.9-0.10.1.jar",
                    "is_alternate": False,
                    "dependencies": []
                },
            ]
        },
    }

    return pool


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


@responses.activate
def test_latest_tree(minecraft, tinkers_construct, available_tinkers_tree):
    """Does the tree resolution works as expected?"""

    for url, jsn in available_tinkers_tree.items():
        responses.add(responses.GET, url, json=jsn)

    resolution = proxy.latest_file_tree(minecraft, tinkers_construct, addon.Release.Release)

    assert len(responses.calls) == 2
    assert len(resolution) == 2
    assert set(f.id for f in resolution) == {2366244, 2353329}
