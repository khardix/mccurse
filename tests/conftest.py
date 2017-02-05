"""Global test configuration"""


import os
from pathlib import Path

import betamax
import pytest

from mccurse import addon, curse
from mccurse.util import yaml


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
def tinkers_construct_file() -> addon.File:
    """Tinkers construct file."""

    yml = """\
    !modfile
    file:
        date: 2016-12-07T18:35:45+00:00
        dependencies: [74924]
        id: 2353329
        name: TConstruct-1.10.2-2.6.1.jar
        release: Release
        url: https://addons.cursecdn.com/files/2353/329/TConstruct-1.10.2-2.6.1.jar
    id: 74072
    name: Tinkers Construct
    summary: Modify all the things, then do it again!
    """

    return yaml.load(yml)


@pytest.fixture
def mantle_file() -> addon.File:
    """Mantle (Tinkers dependency) file."""

    yml = """\
    !modfile
    file:
        date: 2017-01-09T19:40:41+00:00
        dependencies: []
        id: 2366244
        name: Mantle-1.10.2-1.1.4.jar
        release: Release
        url: https://addons.cursecdn.com/files/2366/244/Mantle-1.10.2-1.1.4.jar
    id: 74924
    name: Mantle
    summary: ''
    """

    return yaml.load(yml)


@pytest.fixture
def minecraft() -> curse.Game:
    """Minecraft version for testing."""

    data = {
        'name': 'Minecraft',
        'id': 432,
        'version': '1.10.2',
    }
    return curse.Game(**data)
