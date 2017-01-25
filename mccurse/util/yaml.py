"""PyYAML adaptations and tweaks"""

import re
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from functools import partial
from operator import attrgetter
from typing import Any

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


# Decorator for nicer custom tags
class NodeType(Enum):
    SCALAR = 'construct_scalar', 'represent_scalar'
    SEQUENCE = 'construct_sequence', 'represent_sequence'
    MAPPING = 'construct_mapping', 'represent_mapping'

    def __init__(self: 'NodeType', constructor: str, representer: str) -> None:
        """Remember methodcaller instances for constructor and representer.

        Keyword arguments:
            constructor: Name of the constructor from YAML node.
            representer: Name of the representer to YAML node.
        """

        self.construct = attrgetter(constructor)
        self.represent = attrgetter(representer)


def tag(
    tag: str,
    type: NodeType = NodeType.SCALAR,
    pattern: str = None,
    *,
    Loader=Loader,
    Dumper=Dumper
):
    """Register a YAML tag for a class.

    The class should have defined to_yaml and from_yaml classmethods, with
    following signatures:

    .. py.classmethod:: to_yaml(instance: cls) -> Union[Any,Sequence,Mapping]
                        from_yaml(value: Union[Any,Sequence,Mapping]) -> cls

    Keyword arguments:
        tag: The tag name, should begin with '!'.
        type: Type of the YAML node. Returned and accepted values of to_yaml
            and from_yaml functions should be of compatible type.
        pattern: Optional regex pattern to implicitly resolve to tag.
        Loader: The loader to register to.
        Dumper: The dumper to register to.

    Raises:
        TypeError: When the decorated class does not have to_yaml or from_yaml
            methods.
    """

    def register(cls):
        """Closure registering the passed class."""

        # Test the presence and usability of the functions
        try:
            tested = cls.to_yaml, cls.from_yaml
        except AttributeError:
            raise TypeError('Missing YAML serialization method')

        if not all(isinstance(f, Callable) for f in tested):
            raise TypeError('YAML serialization method(s) are not callable')

        # Make conversion handlers
        def dump(dumper: Dumper, value: Any) -> yaml.Node:
            return type.represent(dumper)(tag, cls.to_yaml(value))

        def load(loader: Loader, node: yaml.Node) -> Any:
            return cls.from_yaml(type.construct(loader)(node))

        # Register conversions
        Dumper.add_representer(cls, dump)
        Loader.add_constructor(tag, load)

        if pattern is not None:
            regexp = re.compile(pattern)
            Dumper.add_implicit_resolver(tag, regexp, None)
            Loader.add_implicit_resolver(tag, regexp, None)

        return cls
    return register


# Provide load and dump functions with registered tweaks and sane defaults
load = partial(yaml.load, Loader=Loader)
dump = partial(yaml.dump, Dumper=Dumper, default_flow_style=False)
