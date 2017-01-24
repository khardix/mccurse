"""Various utilities and language enhancements."""


from datetime import datetime
from functools import partial
from pathlib import Path

import requests
import yaml
import xdg.BaseDirectory
from iso8601 import parse_date

try:
    from yaml import CLoader as YAMLLoader, CDumper as YAMLDumper
except ImportError:
    from yaml import Loader as YAMLLoader, Dumper as YAMLDumper


# Consistent names definitions
RESOURCE_NAME = __package__


# Filesystem standard directories
def default_cache_dir(directory: Path = None) -> Path:
    """Get default cache dir if directory is None,
    else return directory as it is.
    """

    if directory is None:
        return Path(xdg.BaseDirectory.save_cache_path(RESOURCE_NAME))
    else:
        return directory


def default_data_dir(directory: Path = None) -> Path:
    """Get default data dir if directory is None,
    else return directory as it is.
    """

    if directory is None:
        return Path(xdg.BaseDirectory.save_data_path(RESOURCE_NAME))
    else:
        return directory


def default_new_session(session: requests.Session = None) -> requests.Session:
    """Create new Requests' Session, if none is provided.
    Otherwise, return session as it is.
    """

    if session is None:
        return requests.Session()
    else:
        return session


# YAML tweaks

# Force YAML to use ISO-8601 standard for timestamps
def yaml_timestamp_representer(dumper, data):
    """Custom representer for datetime objects in YAML."""
    return dumper.represent_scalar('!!timestamp', data.isoformat())
YAMLDumper.add_representer(datetime, yaml_timestamp_representer)


def yaml_timestamp_constructor(loader, node):
    """Custom constructor for datetime objects from YAML."""
    value = loader.construct_scalar(node)
    return parse_date(value)
YAMLLoader.add_constructor('!!timestamp', yaml_timestamp_constructor)


yamlload = partial(yaml.load, Loader=YAMLLoader)
yamlload.__doc__ = """Load and parse an YAML document."""


yamldump = partial(yaml.dump, Dumper=YAMLDumper, default_flow_style=False)
yamldump.__doc__ = """Dump and store an YAML document."""
