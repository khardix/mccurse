"""Interface to Curse project feed"""


import attr


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

    @property
    def feed_url(self):
        """Expanded feed URL for this game."""

        return FEED_URL.format_map(attr.asdict(self))

    @property
    def timestamp_url(self):
        """Expanded timestamp URL for this game."""

        return TIMESTAMP_URL.format_map(attr.asdict(self))
