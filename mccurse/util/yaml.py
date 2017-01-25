"""PyYAML adaptations and tweaks"""

from datetime import datetime
from functools import partial

import yaml
from iso8601 import parse_date

# Load faster YAML implementation, if possible
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


# Force ISO-8601 timestamps
def timestamp_representer(dumper: Dumper, date: datetime) -> yaml.Node:
    """Custom representer for datetime objects in YAML."""
    return dumper.represent_scalar('!!timestamp', date.isoformat())
Dumper.add_representer(datetime, timestamp_representer)


def timestamp_constructor(loader: Loader, node: yaml.Node) -> datetime:
    """Custom constructor for datetime objects from YAML."""
    value = loader.construct_scalar(node)
    return parse_date(value)
Loader.add_constructor('!!timestamp', timestamp_constructor)


# Provide load and dump functions with registered tweaks and sane defaults
load = partial(yaml.load, Loader=Loader)
dump = partial(yaml.dump, Dumper=Dumper, default_flow_style=False)
