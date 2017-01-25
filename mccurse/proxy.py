"""Interface to the Curse.RestProxy service."""

from enum import Enum, unique
from functools import total_ordering
from typing import Any, TextIO

import attr
import requests
from attr import validators as vld
from requests.auth import AuthBase

from .util import default_new_session, yaml


HOME_URL = 'https://curse-rest-proxy.azurewebsites.net/api'


@attr.s(slots=True)
class Authorization(AuthBase):
    """Authorization mechanism for the proxy service."""

    #: User identification number
    user_id = attr.ib(validator=vld.instance_of(int))
    #: Session token
    token = attr.ib(validator=vld.instance_of(str))

    def __call__(self, req: requests.Request) -> requests.Request:
        """Make the request authenticated."""

        header_fmt = 'Token {user_id}:{token}'
        req.headers['Authorization'] = header_fmt.format_map(attr.asdict(self))

        return req

    @classmethod
    def login(
        cls,
        username: str,
        password: str,
        *,
        session: requests.Session = None
    ) -> 'Authorization':
        """Login into the RestProxy service.

        Keyword arguments:
            username: Name of the user to log in.
            password: Password of the user to log in.
            session: :class:`requests.Session` to use for logging in.

        Returns:
            Authorization for the specified user.

        Raises:
            requests.HTTPError: On invalid credentials.
        """

        session = default_new_session(session)

        url = '/'.join((HOME_URL, 'authenticate'))
        resp = session.post(url, json={
            'username': username,
            'password': password,
        })

        resp.raise_for_status()

        data = resp.json()
        return cls(
            user_id=data['session']['user_id'],
            token=data['session']['token'],
        )

    @classmethod
    def load(cls, file: TextIO) -> 'Authorization':
        """Load stored credentials from file.

        Keyword arguments:
            file: Open YAML text stream to read from.

        Returns:
            Authorization previously saved to the file.

        Raises:
            ValueError: When the stream does not contain expected data.
        """

        data = yaml.load(file)

        if not data or 'user_id' not in data or 'token' not in data:
            msg = 'Invalid authorization data: {!r}'.format(data)
            raise ValueError(msg)

        return cls(**data)

    def dump(self, file: TextIO) -> None:
        """Store credentials for future use.

        Keyword arguments:
            file: Open YAML text stream to write to.
        """

        yaml.dump(attr.asdict(self), file)


@yaml.tag('!release', pattern='^(Alpha|Beta|Release)$')
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

    # Nicer serialization to YAML
    @classmethod
    def from_yaml(cls, name) -> 'Release':
        """Constructs release from an YAML node."""
        return cls[name]

    @classmethod
    def to_yaml(cls, instance):
        """Serialize release to an YAML node."""
        return instance.name
