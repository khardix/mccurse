"""Global test configuration"""


import os
from pathlib import Path

import betamax
import pytest

from mccurse import addon, curse


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
def minecraft() -> curse.Game:
    """Minecraft version for testing."""

    data = {
        'name': 'Minecraft',
        'id': 432,
        'version': '1.10.2',
    }
    return curse.Game(**data)
