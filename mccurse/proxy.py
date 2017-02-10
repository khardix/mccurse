"""Interface to the Curse.RestProxy service."""

from collections import OrderedDict
from operator import attrgetter
from typing import TextIO, Optional, Mapping, Sequence

import attr
import requests
from attr import validators as vld
from requests.auth import AuthBase

from . import _
from .addon import File, Mod, Release
from .exceptions import InvalidStream
from .curse import Game
from .util import default_new_session, yaml, lazydict


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
            InvalidStream: When the stream does not contain expected data.
        """

        data = yaml.load(file)

        if not data or 'user_id' not in data or 'token' not in data:
            msg = _('Invalid authentication data')
            raise InvalidStream(msg, data)

        return cls(**data)

    def dump(self, file: TextIO) -> None:
        """Store credentials for future use.

        Keyword arguments:
            file: Open YAML text stream to write to.
        """

        yaml.dump(attr.asdict(self), file)


def resolve(root: File, pool: Mapping[int, File]) -> OrderedDict:
    """Fully resolve dependecies of a root :class:`addon.File`.

    Keyword arguments:
        root: The `addon.File` to resolve dependencies for.
        pool: Available potential dependencies. Mapping from mod identification
            to corresponding file.

    Returns:
        Ordered mapping of all the dependencies, in breadth-first order,
        including the root. The root is always first in order.
    """

    # Result – resolved dependencies
    resolved = OrderedDict()
    resolved[root.mod.id] = root
    # Which mods needs to be checked
    queue = list(root.dependencies)

    for dep_id in queue:
        if dep_id in resolved:
            continue

        # Get the dependency
        dependency = pool[dep_id]
        # Mark its dependencies for processing
        queue.extend(dependency.dependencies)
        # Add the dependency to chain
        resolved[dep_id] = dependency

    return resolved


def latest(
    game: Game,
    mod: Mod,
    min_release: Release,
    *,
    session: requests.Session = None
) -> Optional[File]:
    """Loads latest suitable addon file data from RestProxy.

    Keyword arguments:
        game: Game (version) to get the file for.
        mod: The mod to get the file for.
        min_release: Minimal release type to consider.
        session: :class:`requests.Session` to use [default: new session].

    Returns:
        Latest available :class:`File`, or None if no file is available.

    Raises:
        requests.HTTPError: On HTTP-related errors.
    """

    # Resolve parameters
    session = default_new_session(session)
    url = HOME_URL + '/addon/{mod.id}/files'.format_map(locals())

    # Get data from proxy
    resp = session.get(url)
    resp.raise_for_status()

    # Filter available files
    available = (
        File.from_proxy(mod, f)
        for f in resp.json()['files']
        if game.version in f['game_version']
    )
    stable = filter(lambda f: f.release >= min_release, available)
    candidates = iter(sorted(stable, key=attrgetter('date'), reverse=True))

    return next(candidates, None)


def latest_file_tree(
    game: Game,
    mod: Mod,
    min_release: Release,
    *,
    session: requests.Session = None
) -> Sequence[File]:
    """Load latest file and all its dependencies for a mod from RestProxy.

    Keyword Arguments:
        game: Game (version) to get the files for.
        mod: The main mod to get files for.
        min_release: Minimal release type to consider.
        session: :class: `requests.Session` to use [default: new session].

    Returns:
        Sequence of files (possibly empty). If it is not empty, it contains
        latest files for requested mod and all its dependencies, with
        file belonging to the requested mod being first.

    Raises:
        requests.HTTPError: On HTTP-related errors.
        sqlalchemy.NoResultsFound: Some necessary mod was not found in game database.
    """

    main = latest(game, mod, min_release, session=session)
    if main is None:  # No file available
        return []

    pool = lazydict(lambda m_id: latest(
        game=game,
        mod=Mod.with_id(game.database.session(), m_id),
        min_release=min_release,
        session=session,
    ))

    return [f for f in resolve(main, pool).values() if f is not None]
