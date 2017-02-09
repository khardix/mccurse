"""Custom exception definitions.

Purpose of this module is to provide usable base classes for more
specialised exceptions in other modules.
"""

import sys
from typing import Mapping, Optional

import click

from . import _
from .util import yaml


class UserReport(click.ClickException):
    """Exception class for errors which should be presented
    to the application user.

    Override format_message() method to show customized text.
    """

    #: Message header
    header = _('Error')

    #: Message color
    color = 'red'

    # Color the output
    def show(self, file=None):
        if file is None:
            file = sys.stderr

        msg = self.format_message()
        click.secho(': '.join((self.header, msg)), file=file, fg=self.color)


class InvalidStream(UserReport):
    """Indicates invalid contents in external data (YAML) stream."""

    slots = 'message', 'errors'

    def __init__(self: 'InvalidStream', msg: str, errors: Optional[Mapping] = None):
        super().__init__(msg)

        self.message = msg
        self.errors = errors

    def format_message(self):
        """Format: {message}:\n{errors}"""

        fmt = [self.message]
        if self.errors is not None:
            fmt.append(yaml.dump(self.errors))

        return ':\n'.join(fmt)


class AlreadyInstalled(UserReport):
    """User requested installation of already installed mod."""

    exit_code = 0

    header = _('Mod is already installed')
    color = 'green'


class NoFileFound(UserReport):
    """No available file found for specified mod and game version."""

    header = _('No available file found for mod')
