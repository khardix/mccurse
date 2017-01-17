"""Interface to the Curse.RestProxy service."""

from typing import TextIO

import attr
import requests
import yaml
from attr import validators as vld
from requests.auth import AuthBase

try:
    from yaml import CLoader as YAMLLoader, CDumper as YAMLDumper
except ImportError:
    from yaml import Loader as YAMLLoader, Dumper as YAMLDumper

from .util import default_new_session


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

        data = yaml.load(file, Loader=YAMLLoader)

        if not data or 'user_id' not in data or 'token' not in data:
            msg = 'Invalid authorization data: {!r}'.format(data)
            raise ValueError(msg)

        return cls(**data)

    def dump(self, file: TextIO) -> None:
        """Store credentials for future use.

        Keyword arguments:
            file: Open YAML text stream to write to.
        """

        yaml.dump(
            attr.asdict(self), file,
            default_flow_style=False,
            Dumper=YAMLDumper,
        )
