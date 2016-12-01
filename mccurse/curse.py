"""Interface to Curse project feed"""


from pathlib import Path
from typing import Iterator

import attr
import requests

from .util import default_new_session, default_cache_dir


# Feed resources URLs
FEED_URL = 'http://clientupdate-v6.cursecdn.com/feed/addons/{id}/v10/complete.json.bz2'  # noqa: E501
TIMESTAMP_URL = 'http://clientupdate-v6.cursecdn.com/feed/addons/{id}/v10/complete.json.bz2.txt'  # noqa: E501

# Local DB URIs
DB_PROTO = 'sqlite://'
DB_BASENAME = 'mods-{abbr}-{timestamp}.sqlite'
DB_URI = '/'.join((DB_PROTO, '{target_dir}', DB_BASENAME))


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
