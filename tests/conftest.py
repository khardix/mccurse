"""Global test configuration"""


import os
from copy import deepcopy
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path

import betamax
import pytest
import responses

from mccurse import addon, curse, proxy


# Ensure cassete dir
CASSETE_DIR = 'tests/cassetes/'
if not os.path.exists(CASSETE_DIR):
    os.makedirs(CASSETE_DIR)

record_mode = 'none' if os.environ.get('TRAVIS_BUILD') else 'once'

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = CASSETE_DIR
    config.default_cassette_options.update({
        'record_mode': record_mode,
        'preserve_exact_body_bytes': True,
    })


# Shared fixtures
@pytest.fixture
def file_database(tmpdir) -> curse.Database:
    """Database potentially located in temp dir."""

    return curse.Database('test', Path(str(tmpdir)))


@pytest.fixture(scope='session')
def tinkers_construct() -> addon.Mod:
    """Tinkers Construct project data"""

    data = {
        'name': 'Tinkers Construct',
        'id': 74072,
        'summary': 'Modify all the things, then do it again!',
    }
    return addon.Mod(**data)


@pytest.fixture(scope='session')
def mantle() -> addon.Mod:
    """Mantle (Tinkers Construct dependency) project data"""

    return addon.Mod(id=74924, name='Mantle', summary='')


@pytest.fixture
def tinkers_construct_file(tinkers_construct) -> addon.File:
    """Tinkers construct file."""

    return addon.File(
        id=2338518,
        mod=tinkers_construct,
        name='TConstruct-1.10.2-2.5.6b.jar',
        date=datetime(
            year=2016, month=10, day=22,
            hour=15, minute=11, second=19,
            tzinfo=timezone.utc,
        ),
        release=proxy.Release.Release,
        url='https://addons.cursecdn.com/files/2338/518/TConstruct-1.10.2-2.5.6b.jar',
        dependencies=[74924],
    )


@pytest.fixture
def tinkers_update(tinkers_construct) -> addon.File:
    """Update for tinkers_construct_file."""

    return addon.File(
        id=2353329,
        mod=tinkers_construct,
        name='TConstruct-1.10.2-2.6.1.jar',
        date=datetime(
            year=2016, month=12, day=7,
            hour=18, minute=35, second=45,
            tzinfo=timezone.utc,
        ),
        release=proxy.Release.Release,
        url='https://addons.cursecdn.com/files/2353/329/TConstruct-1.10.2-2.6.1.jar',
        dependencies=[74924],
    )


@pytest.fixture
def mantle_file(mantle) -> addon.File:
    """Mantle (Tinkers dependency) file."""

    return addon.File(
        id=2366244,
        mod=mantle,
        name='Mantle-1.10.2-1.1.4.jar',
        date=datetime(
            year=2017, month=1, day=9,
            hour=19, minute=40, second=41,
            tzinfo=timezone.utc,
        ),
        release=proxy.Release.Release,
        url='https://addons.cursecdn.com/files/2366/244/Mantle-1.10.2-1.1.4.jar',
        dependencies=[],
    )


@pytest.fixture(scope='session')
def minecraft(tmpdir_factory, tinkers_construct, mantle) -> curse.Game:
    """Minecraft version for testing."""

    dbdir = Path(str(tmpdir_factory.mktemp('testdbs')))

    game = curse.Game(id=432, name='Minecraft', version='1.10.2', cache_dir=dbdir)

    sql_session = game.database.session()
    sql_session.add(deepcopy(tinkers_construct))
    sql_session.add(deepcopy(mantle))
    sql_session.commit()

    return game


@pytest.fixture
def available_files() -> dict:
    """Test set of available files for Tinkers Construct.

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
def available_tinkers_tree(tinkers_construct, mantle_file) -> responses.RequestsMock:
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

    requests_mock = responses.RequestsMock(assert_all_requests_are_fired=False)
    for url, jsn in pool.items():
        requests_mock.add(responses.GET, url, json=jsn)

    # Add dummy file contents
    for file in chain.from_iterable(v['files'] for v in pool.values()):
        url = file['download_url']
        content = url.split('/')[-1].encode('utf-8')
        requests_mock.add(responses.GET, url, body=content)

    return requests_mock
