"""Mod-pack file format interface."""

from enum import Enum, unique
from functools import total_ordering
from typing import Any, Callable

import cerberus
from iso8601 import parse_date as isodate


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
