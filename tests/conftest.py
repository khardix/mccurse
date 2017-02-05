"""Global test configuration"""


import os
from datetime import datetime, timezone
from pathlib import Path

import betamax
import pytest

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


@pytest.fixture
def tinkers_construct() -> addon.Mod:
    """Tinkers Construct project data"""

    data = {
        'name': 'Tinkers Construct',
        'id': 74072,
        'summary': 'Modify all the things, then do it again!',
    }
    return addon.Mod(**data)


@pytest.fixture
def tinkers_construct_file(tinkers_construct) -> addon.File:
    """Tinkers construct file."""

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
def mantle_file() -> addon.File:
    """Mantle (Tinkers dependency) file."""

    return addon.File(
        id=2366244,
        mod=addon.Mod(id=74924, name='Mantle', summary=''),
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


@pytest.fixture
def minecraft() -> curse.Game:
    """Minecraft version for testing."""

    data = {
        'name': 'Minecraft',
        'id': 432,
        'version': '1.10.2',
    }
    return curse.Game(**data)
