"""Minecraft Curse CLI Client"""

import gettext
from pathlib import Path

#: Consistent names definitions
RESOURCE_NAME = __package__

#: Root of the package
pkgdir = Path(__file__).resolve().parent

#: Root of the locale files
localedir = pkgdir / '_data_' / 'locales'

#: Translation machinery for the app
translation = gettext.translation(
    domain=__package__,
    # Allow the locale files to be stored in system folder
    localedir=str(localedir) if localedir.is_dir() else None,
    fallback=True,
)
_ = translation.gettext
