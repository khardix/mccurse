"""Custom exception definitions.

Purpose of this module is to provide usable base classes for more
specialised exceptions in other modules.
"""

import sys
from typing import Mapping, Optional

import click

from . import _
from util import yaml


class UserReport(click.ClickException):
    """Exception class for errors which should be presented
    to the application user.

    Override format_message() method to show customized text.
    """

    # Color the output
    def show(self, file=None):
        if file is None:
            file = sys.stderr

        header = click.style(_('Error:'), fg='red')
        msg = self.format_message()

        click.echo(' '.join((header, msg)), file=file)


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
