"""Interface to CurseForge.

This module contains definitons of classes wrapping project feeds, games
and any other resources available from the Curse network.
"""


import bz2
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterator, TextIO

import attr
import requests
from attr import validators as vld

from .util import default_new_session, default_cache_dir


# Feed resources URLs
FEED_URL = 'http://clientupdate-v6.cursecdn.com/feed/addons/{id}/v10/complete.json.bz2'  # noqa: E501
TIMESTAMP_URL = 'http://clientupdate-v6.cursecdn.com/feed/addons/{id}/v10/complete.json.bz2.txt'  # noqa: E501

# Local DB URIs
DB_PROTO = 'sqlite://'
DB_BASENAME = 'mods-{abbr}-{timestamp}.sqlite'
DB_URI = '/'.join((DB_PROTO, '{target_dir}', DB_BASENAME))


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


@attr.s(slots=True)
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


@attr.s(slots=True)
class Game:
    """Description of a moddable game for the Curse feed."""

    id = attr.ib(validator=attr.validators.instance_of(int))
    abbr = attr.ib(validator=attr.validators.instance_of(str))
    name = attr.ib(validator=attr.validators.instance_of(str))

    session = attr.ib(  # mainly for timestamp querying
        validator=attr.validators.optional(
            attr.validators.instance_of(requests.Session)
        ),
        default=None,
    )

    @property
    def feed_url(self):
        """Expanded feed URL for this game."""

        return FEED_URL.format_map(attr.asdict(self))

    @property
    def timestamp_url(self):
        """Expanded timestamp URL for this game."""

        return TIMESTAMP_URL.format_map(attr.asdict(self))

    def current_timestamp(self) -> int:
        """Fetch current timestamp."""

        session = default_new_session(self.session)
        resp = session.get(self.timestamp_url)
        resp.raise_for_status()

        return int(resp.text)

    def db_uri(self, target_dir: Path = None, timestamp: int = None) -> str:
        """Expand DB URI.

        Keyword arguments:
            target_dir -- Path to the dir where the DB is located
                [default: cache dir].
            timestamp -- Timestamp to use [default: current timestamp].

        Returns:
            Fully expanded DB URI.
        """

        target_dir = default_cache_dir(target_dir)
        if timestamp is None:
            timestamp = self.current_timestamp()

        return DB_URI.format(
            target_dir=str(target_dir),
            abbr=self.abbr,
            timestamp=timestamp,
        )

    def db_glob(self, target_dir: Path = None) -> Iterator[Path]:
        """Glob all DB and return iterator over them.

        Keyword arguments:
            target_dir -- Path to the dir wehere the DBs are located
                [default: cache dir].

        Returns:
            Iterator over Paths to existing databases.
        """

        target_dir = default_cache_dir(target_dir)

        glob = DB_BASENAME.format(abbr=self.abbr, timestamp='*')
        return target_dir.glob(glob)
