"""Tests for util submodule."""


from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
import xdg

from mccurse import util
from mccurse.util import yaml


def test_expected_resource_name():
    """Is the RESOURCE_NAME equivalent to the root package?"""

    assert util.RESOURCE_NAME == 'mccurse'


def test_cache_use_default():
    """Use cache dir when no dir specified?"""

    INPUT = None
    EXPECT = Path(xdg.BaseDirectory.save_cache_path(util.RESOURCE_NAME))

    assert util.default_cache_dir(INPUT) == EXPECT


def test_cache_use_input():
    """Use existing dir when specified?"""

    INPUT = Path.home()
    EXPECT = INPUT

    assert util.default_cache_dir(INPUT) == EXPECT


def test_data_use_default():
    """Use data dir when no dir specified?"""

    INPUT = None
    EXPECT = Path(xdg.BaseDirectory.save_data_path(util.RESOURCE_NAME))

    assert util.default_data_dir(INPUT) == EXPECT


def test_data_use_input():
    """Use existing dir when specified?"""

    INPUT = Path.home()
    EXPECT = INPUT

    assert util.default_data_dir(INPUT) == EXPECT


def test_use_existing_session():
    """Use existing session when specified?"""

    INPUT = requests.Session()
    EXPECT = INPUT

    assert util.default_new_session(INPUT) is EXPECT


def test_make_new_session():
    """Make new session when none provided?"""

    INPUT = None

    assert isinstance(util.default_new_session(INPUT), requests.Session)


@pytest.mark.parametrize('key,value', [
    (42, 42),
    ('42', 42),
])
def test_lazydict_valid(key, value):
    """Lazydict functions as expected?"""

    d = util.lazydict(int)

    assert d[key] == value


@pytest.mark.parametrize('key,exception', [
    ('abc', ValueError),
])
def test_lazydict_exceptions(key, exception):
    """Lazydict not consuming excpetions?"""

    d = util.lazydict(int)

    with pytest.raises(exception):
        x = d[key]  # noqa


def test_yaml_datetime():
    """Custom datetime serialization works as expected?"""

    now = datetime.now(tz=timezone.utc)

    assert now.isoformat() in yaml.dump(now)
    assert yaml.load(now.isoformat()) == now


def test_yaml_path():
    """Custom path serialization working as expected?"""

    path = Path('some/long/path')

    assert str(path) in yaml.dump(path)
