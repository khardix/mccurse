"""Interface to CurseForge.

This module contains definitons of classes wrapping project feeds, games
and any other resources available from the Curse network.
"""


import bz2
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import TextIO, Type, Mapping

import attr
import ijson
import requests
import sqlalchemy
from attr import validators as vld
from sqlalchemy.orm.session import Session as SQLSession

from . import _, PKGDATA
from .addon import AddonBase, Mod
from .util import default_new_session, default_cache_dir, yaml

# Used exceptions -- make them available in this namespace
from requests.exceptions import HTTPError  # noqa: F401

SUPPORTED_GAMES = PKGDATA / 'supported_games.yaml'


@attr.s(slots=True)
class Feed:
    """Interface to the Curse Project Feed for a particular game.

    The project feed is a set of bzip2-compressed json files that
    contains all of the add-ons for a game. The set consists of
    a complete feed (`complete.json.bz2`) and a hourly feed
    (`hourly.json.bz2`). Both feeds contain a timestamp of last change
    (in ms, for some reason), which is also accessible separately by
    appending a `.txt` suffix to the feed URL (i.e.
    `complete.json.bz2.txt`).
    """

    #: Base URL
    _BASEURL = 'http://clientupdate-v6.cursecdn.com/feed/addons/{id}/v10'
    #: Complete feed suffix
    _COMPLETE_URL = 'complete.json.bz2'

    #: Curse internal game identification
    game_id = attr.ib(validator=vld.instance_of(int))
    #: The :class:`requests.Session` to use for network requests
    session = attr.ib(
        validator=vld.optional(vld.instance_of(requests.Session)),
        default=None,
    )

    @property
    def complete_url(self) -> str:
        """Fully expanded URL of complete feed."""

        parts = (
            self._BASEURL.format(id=self.game_id),
            self._COMPLETE_URL,
        )

        return '/'.join(parts)

    @property
    def complete_timestamp_url(self) -> str:
        """Fully expanded URL of complete feed timestamp."""

        return self.complete_url + '.txt'

    @staticmethod
    @contextmanager
    def _decode_contents(feed: bytes) -> TextIO:
        """Decode the provided data from bz2 to text.

        The :arg:`feed` is assumed to be bz2-encoded text data in utf-8
        encoding.

        Keyword arguments:
            feed: The data to be decoded.

        Returns: Decoded text stream.
        """

        with BytesIO(feed) as compressed, \
                bz2.open(compressed, mode='rt', encoding='utf-8') as stream:
            yield stream

    @contextmanager
    def fetch_complete(self) -> TextIO:
        """Provide complete feed contents.

        Returns:
            Text stream of complete feed contents, that should be used
            in with-statement to be closed afterwards.

        Raises:
            requests.HTTPError: When an HTTP error occurs when fetching feed.
        """

        session = default_new_session(self.session)

        resp = session.get(self.complete_url)
        resp.raise_for_status()

        with self._decode_contents(resp.content) as text:
            yield text

    @staticmethod
    def _decode_timestamp(ms_timestamp: int) -> datetime:
        """Convert timestamp in ms into a :class:`datetime` object.

        Keyword arguments:
            ms_timestamp: The timestamp, in miliseconds, presumed to be in UTC.

        Returns:
            :class:`datetime` object pointing to the same point in time
            as the timestamp.
        """

        return datetime.fromtimestamp(ms_timestamp/1000, timezone.utc)

    def fetch_complete_timestamp(self) -> datetime:
        """Provide current complete feed time signature.

        .. note:: The timestamp is assumed to be in UTC (as it should be).

        Returns:
            Datetime object pointed to the same point in time as the timestamp.

        Raises:
            requests.HTTPError: When an HTTP error occurs while fetching.
        """

        session = default_new_session(self.session)

        resp = session.get(self.complete_timestamp_url)
        resp.raise_for_status()

        return self._decode_timestamp(int(resp.content))


@attr.s(slots=True, cmp=False)
class Database:
    """Interface to the local database of addons for a particular game.

    The addon database is stored in SQLite3 DB file. Its main purpose is to
    store feed's data locally and to prevent unnecessary re-downloading
    and re-parsing of them.

    The timestamp of the data can (and should) be stored directly
    in the DB file header (using `pragma user_version`). However, this only
    accepts 32 bits wide integer, so the timestamp should be stored
    fractionless (floored to whole second), and it is vulnerable
    to the "Year 2038" problem.
    """

    _SCHEME = 'sqlite://'  #: DB URI scheme.
    _BASENAME = '{game_name}-addons.sqlite'  #: DB URI basename format

    #: Name uniquely identifiyng the game.
    game_name = attr.ib(validator=vld.instance_of(str))
    #: Location of the database on the filesystem.
    root_dir = attr.ib(validator=vld.instance_of(Path))

    @property
    def uri(self) -> str:
        """Constructs full DB URI for this database."""

        return '/'.join((
            self._SCHEME,
            str(self.root_dir.resolve()),
            self._BASENAME.format(game_name=self.game_name),
        ))

    @property
    @lru_cache()
    def engine(self) -> sqlalchemy.engine.Engine:
        """Provide connection pool for the database."""

        return sqlalchemy.create_engine(self.uri)

    @property
    def version(self) -> datetime:
        """Read the version/timestamp of the data in the database."""

        timestamp, = self.engine.execute('PRAGMA user_version').first()
        return datetime.fromtimestamp(timestamp, timezone.utc)

    @version.setter
    def version(self, newver: datetime) -> None:
        """Set the version/timestamp of the data in the database."""

        # Cannot use SQL interpolation in PRAGMA statements :(
        # Force integral formating that the value is indeed an integer
        query = 'PRAGMA user_version = {:d}'.format(int(newver.timestamp()))
        with self.engine.begin() as conn:
            conn.execute(query)

    def session(self) -> SQLSession:
        """Create new session for batch database communication."""

        return SQLSession(bind=self.engine)


class UnsupportedGameError(ValueError):
    """Attempt to instantiate game which is not supported."""


@yaml.tag('!game', type=yaml.NodeType.MAPPING)
@attr.s(init=False, slots=True)
class Game:
    """Interface to the projects related to one game in Curse network.

    The purpose of this class is to aggregate any objects providing related
    functionality and provide high-level procedural "glue" tying them
    together in one neat package.
    """

    # Primary attributes – must be supplied by user
    id = attr.ib(validator=vld.instance_of(int))  #: Curse internal game ID
    name = attr.ib(validator=vld.instance_of(str))  #: Human-readable name
    version = attr.ib(validator=vld.instance_of(str))  #: Game version

    # Secondary/Derived attributes
    database = attr.ib(validator=vld.instance_of(Database), cmp=False)
    feed = attr.ib(validator=vld.instance_of(Feed), cmp=False)

    def __init__(
        self,
        id: int,
        name: str,
        version: str,
        *,
        session: requests.Session = None,
        cache_dir: Path = None
    ):
        """Initialize and create all the data for a game.

        Keyword arguments:
            id: Curse internal game identification.
            name: Human-readable name.
            version: Game version.
            session: :class:`requests.Session` to use for network calls.
            cache_dir: Path to the game's cache (which include mod database).
        """

        session = default_new_session(session)
        cache_dir = default_cache_dir(cache_dir)

        self.id = id
        self.name = name
        self.version = version

        self.database = Database(game_name=name.lower(), root_dir=cache_dir)
        self.feed = Feed(game_id=id, session=session)

        # Fill the database, if it does not exists
        epoch = datetime.fromtimestamp(0, tz=timezone.utc)
        if self.database.version == epoch:
            AddonBase.metadata.create_all(self.database.engine)

    @classmethod
    def find(cls: Type['Game'], name: str, *, gamedb: Path = SUPPORTED_GAMES) -> 'Game':
        """Find and create instance of a supported game.

        Keyword arguments:
            name: Name of the game to instantiate.
            gamedb: Path to the YAML dictionary of supported games.

        Returns:
            Instance of the supported game.

        Raises:
            UnsupportedGameError: When the name is not found among supported games.
        """

        with gamedb.open(encoding='utf-8') as gamestream:
            games = yaml.load(gamestream)

        defaults = games.get(name.lower(), None)
        if defaults is None:
            msg = _("Game not supported: '{name}'").format_map(locals())
            raise UnsupportedGameError(msg)

        return cls(name=name.capitalize(), **defaults)

    @classmethod
    def from_yaml(cls: Type['Game'], data: Mapping) -> 'Game':
        """Construct new instance from YAML data."""

        instance = cls.find(data['name'])

        # Replace game defaults with supplied values
        for attrib, value in data.items():
            setattr(instance, attrib, value)

        return instance

    @classmethod
    def to_yaml(cls: Type['Game'], instance: 'Game') -> Mapping:
        """Serialize an instance to YAML data."""

        # Serialize only relevant parts
        return {
            'name': instance.name,
            'version': instance.version,
        }

    def refresh_data(self):
        """Download, store and index fresh version of the game add-ons."""

        sess = self.database.session()

        # Destroy indexes and truncate old data
        sess.query(Mod).delete()

        # Parse the feed's data
        # TODO: Extract feed's timestamp from the JSON
        with self.feed.fetch_complete() as feed:
            addons = ijson.items(feed, 'data.item')
            mods = filter(
                lambda a: a['CategorySection']['Path'] == 'mods',
                addons,
            )

            sess.add_all(Mod.from_json(m) for m in mods)

        sess.commit()

        # Write the timestamp
        self.database.version = self.feed.fetch_complete_timestamp()

    def have_fresh_data(
        self,
        valid_period: timedelta = timedelta(hours=24),
        *,
        now: datetime = datetime.now(tz=timezone.utc)
    ) -> bool:
        """Check if the data in the database are still fresh (enough).

        By default, the data are considered to be actual for 24 hours
        after the publication of the project feed.

        Keyword arguments:
            valid_period: How much time has to pass since the data import
                for the data to be considered stale.
            now: Specify the point in time to be considered 'now'.

        Returns:
            True if the data are still considered fresh, False otherwise.
        """

        time_passed = now - self.database.version
        return time_passed < valid_period
