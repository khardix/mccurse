"""Various utilities and language enhancements."""


from pathlib import Path

import requests
import xdg.BaseDirectory


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
