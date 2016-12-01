"""Various utilities and language enhancements."""


from pathinfo import Path

import xdg


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
