"""Mod-pack file format interface."""

from collections import OrderedDict
from copy import deepcopy
from typing import Mapping, TextIO

import cerberus

from .addon import File
from .curse import Game
from .util import yaml, cerberus as crb


# Game schema
cerberus.schema_registry.add('game', {
    'name': {'type': 'string'},
    'version': {'type': 'string'},
})

# Pack file schema
cerberus.schema_registry.add('pack', {
    'game': {'type': 'dict', 'schema': 'game', 'required': True},
    'mods': {'type': 'list', 'schema': {
        'validator': crb.instance_of(File), 'coerce': crb.fromyaml(File),
    }},
    'dependencies': {'type': 'list', 'schema': {
        'validator': crb.instance_of(File), 'coerce': crb.fromyaml(File),
    }},
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


def resolve(root: File, pool: Mapping[int, File]) -> OrderedDict:
    """Fully resolve dependecies of a root :class:`addon.File`.

    Keyword arguments:
        root: The `addon.File` to resolve dependencies for.
        pool: Available potential dependencies. Mapping from mod identification
            to corresponding file.

    Returns:
        Ordered mapping of all the dependencies, in breadth-first order,
        including the root.
    """
