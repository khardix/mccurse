"""Minecraft Curse CLI Client"""

import gettext
import logging
from pathlib import Path

from colorlog import ColoredFormatter

#: Consistent names definitions
RESOURCE_NAME = __package__

#: Root of the package
PKGDIR = Path(__file__).resolve().parent

#: Package data directory
PKGDATA = PKGDIR / '_data_'

#: Root of the locale files
localedir = PKGDATA / 'locales'

#: Translation machinery for the app
translation = gettext.translation(
    domain=__package__,
    # Allow the locale files to be stored in system folder
    localedir=str(localedir) if localedir.is_dir() else None,
    fallback=True,
)
_ = translation.gettext

#: Logging machinery for the app
color_log_fmt = ColoredFormatter(
    '%(log_color)s%(message)s',
    style='%',
    reset=True,
    log_colors={
        'DEBUG': 'purple',
        'INFO': 'reset',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'fg_red,bg_white',
    },
)
color_console_handler = logging.StreamHandler()
color_console_handler.setFormatter(color_log_fmt)

log = logging.getLogger(RESOURCE_NAME)
log.addHandler(color_console_handler)
