"""Minecraft Curse CLI Client"""

import gettext
from pathlib import Path

pkgdir = Path(__file__).resolve().parent

localedir = pkgdir/'locales'

translation = gettext.translation(
    __package__,
    localedir=str(localedir) if localedir.exists() else None,
)
_ = translation.gettext
