"""Custom wrappers, validators and coercers for the cerberus library."""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Type, TypeVar, Union

from iso8601 import parse_date


# Named generic types
ErrorCallback = Callable[[Any, str], None]
T = TypeVar('T')


# Custom validators
def instance_of(cls: Type) -> Callable[[Any, Any, ErrorCallback], bool]:
    """Create validator for an arbitrary type.

    Keyword arguments:
        cls: The type to check the instance against.

    Returns:
        Validator callable.
    """

    def validate(field: Any, value: Any, error: ErrorCallback) -> bool:
        if isinstance(value, cls):
            return True
        else:
            msg = "Value '{!s}' is not of type '{!s}'".format(
                value, cls.__name__,
            )
            error(field, msg)
            return False

    return validate


# Custom coercers
def isodate(value: Union[str, datetime]) -> datetime:
    """Coerce ISO-8601 date string to `class`:datetime:, if needed.

    Keyword arguments:
        value: The string to be coerced. Alternatively, if the value is
            already `class`:datetime:, pass it unchanged.

    Returns:
        Coerced value.
    """

    if isinstance(value, str):
        return parse_date(value)
    else:  # Do not perform validation, it is different task
        return value


def fromname(cls: Type[Enum]) -> Callable[[Union[str, Enum]], Enum]:
    """Create coercer for an arbitrary `class`:Enum: from its possible names.

    Keyword arguments:
        cls: The enumeration to coerce to.

    Returns:
        Coercer which converts string values to appropriate enumeration,
        or pass the value unchanged.
    """

    def coerce(value: Union[str, Enum]) -> Enum:
        if isinstance(value, str):
            return cls[value]
        else:
            return value

    return coerce


def fromyaml(cls: Type[T]) -> Callable[[Any], T]:
    """Create coercer for an arbitrary type that can be constructed from YAML.

    Keyword arguments:
        cls: The type to coerce to.

    Returns:
        Coercer which tries to convert to appropriate type, leaving values
        already of that type unchanged.
    """

    def coerce(value: Any) -> T:
        if isinstance(value, cls):
            return value
        else:
            return cls.from_yaml(value)

    return coerce
