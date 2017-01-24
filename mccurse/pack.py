"""Mod-pack file format interface."""

from copy import deepcopy
from enum import Enum, unique
from functools import total_ordering
from typing import Any, Callable, TextIO

import cerberus
from iso8601 import parse_date as isodate

from .util import yamlload, yamldump


@unique
@total_ordering
class Release(Enum):
    """Enumeration of the possible release types of a mod file."""

    Alpha = 1
    Beta = 2
    Release = 4

    # Make the releases comparable
    def __is_same_enum(self: 'Release', other: Any) -> bool:
        """Detect if the compared value is of the same class."""
        return other.__class__ is self.__class__

    def __eq__(self: 'Release', other: 'Release') -> bool:
        if self.__is_same_enum(other):
            return self.value == other.value
        else:
            return NotImplemented

    def __ne__(self: 'Release', other: 'Release') -> bool:
        if self.__is_same_enum(other):
            return self.value != other.value
        else:
            return NotImplemented

    def __lt__(self: 'Release', other: 'Release') -> bool:
        if self.__is_same_enum(other):
            return self.value < other.value
        else:
            return NotImplemented


# Custom cerberus validators
def valid_release(field: str, value: Any, error: Callable) -> bool:
    """Validate Release type."""
    if isinstance(value, Release):
        return True
    else:
        error(field, "Not a valid release: '{!s}'".format(value))


# Mod file schema
cerberus.schema_registry.add('mod-file', {
    'id': {'type': 'integer', 'required': True, 'coerce': int},
    'name': {'type': 'string', 'required': True},
    'date': {'type': 'datetime', 'required': True, 'coerce': isodate},
    'release': {'validator': valid_release, 'required': True, 'coerce': Release.__getitem__},  # noqa: E501
    'dependencies': {'type': 'list', 'schema': {'type': 'integer'}},
})

# Mod schema
cerberus.schema_registry.add('mod', {
    'id': {'type': 'integer', 'required': True, 'coerce': int},
    'name': {'type': 'string'},
    'file': {'type': 'dict', 'schema': 'mod-file', 'required': True},
})

# Game schema
cerberus.schema_registry.add('game', {
    'name': {'type': 'string'},
    'version': {'type': 'string'},
})

# Pack file schema
cerberus.schema_registry.add('pack', {
    'game': {'type': 'dict', 'schema': 'game', 'required': True},
    'mods': {'type': 'list', 'schema': {'type': 'dict', 'schema': 'mod'}},
    'dependencies': {'type': 'list', 'schema': {'type': 'dict', 'schema': 'mod'}},  # noqa: E501
})


class ValidationError(ValueError):
    """Exception for reporting invalid pack data."""

    __slots__ = 'errors',

    def __init__(self, msg: str, errors: dict):
        super().__init__(msg)
        self.errors = errors


class ModPack:
    """Interface to single mod-pack data."""

    __slots__ = 'data',

    def __init__(self, data: dict):
        """Validate data for the mod-pack.

        Raises:
            ValidationError: If the data are not valid mod-pack data.
        """

        vld = cerberus.Validator(cerberus.schema_registry.get('pack'))
        # Do NOT change input data during validation!
        if not vld.validate(deepcopy(data)):
            raise ValidationError('Invalid pack data', vld.errors)

        self.data = vld.document

    @classmethod
    def create(cls, name: str, version: str) -> 'ModPack':
        """Create new, empty mod-pack.

        Keyword arguments:
            name: Name of the game to make pack for.
            version: Version of the game to make pack for.

        Returns:
            Newly created mod-pack.
        """

        return cls({
            'game': {
                'name': name,
                'version': version,
            },
        })

    @classmethod
    def from_yaml(cls, stream: TextIO) -> 'ModPack':
        """Load mod-pack data from a file stream.

        Keyword arguments:
            stream: Input YAML stream.

        Returns:
            Mod-pack loaded form the stream.

        Raises:
            ValidationError: If the stream does not contain valid pack data.
        """

        return cls(yamlload(stream))

    def to_yaml(self, stream: TextIO) -> None:
        """Serialize and save the mod-pack data to YAML stream.

        Keyword arguments:
            stream: The YAML stream to write to.
        """

        yamldump(self.data, stream)
