"""Various utilities and language enhancements."""


from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Hashable

import requests
import xdg.BaseDirectory

from .. import RESOURCE_NAME


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


class lazydict(defaultdict):
    """Dictionary which lazily construct values on missing keys."""

    def __init__(self: 'lazydict', value_factory: Callable[[Hashable], Any]=None, *args, **kw):
        """Initialize new lazy dictionary.

        Keyword arguments:
            value_factory: The callable to use for constructing
                missing values.
            Other arguments are the same as for built-in `dict`.
        """

        self.value_factory = value_factory
        super().__init__(None, *args, **kw)

    def __missing__(self: 'lazydict', key: Hashable) -> Any:
        """Attempts to construct the value and inserts it into the dictionary."""

        if self.value_factory is None:
            raise KeyError(key)

        value = self.value_factory(key)

        self[key] = value
        return value
