"""Mod-pack file format interface."""

from copy import deepcopy
from typing import TextIO

import cerberus

from .curse import Game
from .proxy import Release
from .util import yaml, cerberus as crb


# Mod file schema
cerberus.schema_registry.add('mod-file', {
    'id': {'type': 'integer', 'required': True, 'coerce': int},
    'name': {'type': 'string', 'required': True},
    'date': {'type': 'datetime', 'required': True, 'coerce': crb.isodate},
    'release': {'validator': crb.instance_of(Release), 'required': True, 'coerce': crb.fromname(Release)},  # noqa: E501
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
    def create(cls, game: Game) -> 'ModPack':
        """Create new, empty mod-pack.

        Keyword arguments:
            name: Name of the game to make pack for.
            version: Version of the game to make pack for.

        Returns:
            Newly created mod-pack.
        """

        return cls({
            'game': {
                'name': game.name,
                'version': game.version,
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

        return cls(yaml.load(stream))

    def to_yaml(self, stream: TextIO) -> None:
        """Serialize and save the mod-pack data to YAML stream.

        Keyword arguments:
            stream: The YAML stream to write to.
        """

        yaml.dump(self.data, stream)
