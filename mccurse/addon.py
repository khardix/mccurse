"""Objects storing data or information related to add-ons
   (i.e. Mod, mod's File, etc.).
"""

from datetime import datetime
from enum import Enum, unique
from functools import total_ordering
from typing import Any, Mapping, Sequence, Type

import attr
from attr import validators as vld
from iso8601 import parse_date
from sqlalchemy import Column, Integer, String
from sqlalchemy import or_, bindparam
from sqlalchemy.ext.baked import bakery
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.session import Session as SQLSession

# Used exceptions -- make them available in current namespace
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound  # noqa: F401

from .util import yaml

# Declarative base class for DB table definitions
AddonBase = declarative_base()
# Cache for pre-compiling SQL queries
SQLBakery = bakery()


class Mod(AddonBase):
    """Single game modification data adapter.

    This class serves as the adapter between JSON in the project feed
    and the local database.
    """

    __tablename__ = 'mods'

    #: Internal Curse mod identification
    id = Column(Integer, primary_key=True, autoincrement=False)
    #: Official mod name
    name = Column(String, index=True)
    #: Short mod description
    summary = Column(String, index=True)

    def __repr__(self) -> str:
        fmt = 'Mod(id={0.id!r}, name={0.name!r}, summary={0.summary!r})'
        return fmt.format(self)

    def __eq__(self, other: 'Mod') -> bool:
        if not isinstance(other, Mod):
            return NotImplemented

        partials = (
            self.id == other.id,
            self.name == other.name,
            self.summary == other.summary,
        )
        return all(partials)

    # Adapter methods

    @classmethod
    def from_json(cls, jobj: Mapping) -> 'Mod':
        """Construct new instance from JSON.

        Keyword arguments:
            jobj: The JSON data to use.

        Returns:
            New instance.
        """

        fields = 'id', 'name', 'summary'

        data = {k: jobj[k.capitalize()] for k in fields}
        return cls(**data)

    # Prepared queries

    @classmethod
    def search(cls, connection: SQLSession, term: str) -> Sequence['Mod']:
        """Search for Mods that contain TERM in name or summary.

        Keyword arguments:
            connection: Database connection to ask on.
            term: The term to search for.

        Returns:
            Sequence of matching mods (possibly empty).
        """

        query = SQLBakery(lambda conn: conn.query(cls))
        query += lambda q: q.filter(or_(
            cls.name.like(bindparam('term')),
            cls.summary.like(bindparam('term')),
        ))
        query += lambda q: q.order_by(cls.name)

        return query(connection).params(term='%{}%'.format(term)).all()

    @classmethod
    def find(cls, connection: SQLSession, name: str) -> 'Mod':
        """Find exactly one Mod named NAME.

        Keyword Arguments:
            connection: Database connection to ask on.
            name: The name of the mod to search for.

        Returns:
            The requested mod.

        Raises:
            NoResultsFound: The name does not match any known mod.
            MultipleResultsFound: The name is too ambiguous,
                multiple matching mods found.
        """

        query = SQLBakery(lambda conn: conn.query(cls))
        query += lambda q: q.filter(cls.name.like(bindparam('name')))

        return query(connection).params(name='{}'.format(name)).one()

    @classmethod
    def with_id(cls, connection: SQLSession, id: int) -> 'Mod':
        """Fetch mod with id from database.

        Keyword arguments:
            connection: Database connection to fetch from.
            id: The id field of the mod to get.

        Returns:
            The requested mod.

        Raises:
            NoResultFound: Mod with specified id does not exist.
        """

        query = SQLBakery(lambda conn: conn.query(cls))
        query += lambda q: q.filter(cls.id == bindparam('id'))

        return query(connection).params(id=id).one()


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


@yaml.tag('!modfile', type=yaml.NodeType.MAPPING)
@attr.s(slots=True, frozen=True)
class File:
    """Metadata of a file belonging to some mod."""

    # Data for hashing: id, name, date

    #: File identification
    id = attr.ib(validator=vld.instance_of(int))
    #: Associated mod identification
    mod = attr.ib(validator=vld.instance_of(Mod), hash=False)
    #: File system base name
    name = attr.ib(validator=vld.instance_of(str))
    #: Publication date
    date = attr.ib(validator=vld.instance_of(datetime))
    #: Release type
    release = attr.ib(validator=vld.instance_of(Release), hash=False)
    #: Remote URL for download
    url = attr.ib(validator=vld.instance_of(str), hash=False)
    #: Dependencies; {mod_id: File}
    dependencies = attr.ib(
        validator=vld.optional(vld.instance_of(list)),
        default=attr.Factory(list),
        hash=False,
    )

    @classmethod
    def from_proxy(cls: Type['File'], mod: Mod, data: Mapping) -> 'File':
        """Construct new File from RestProxy-compatible JSON data.

        Keyword arguments:
            mod: Either mod identification (int), or the mod (Mod)
                to associate this file with.
            data: The data to construct new File from.

        Returns:
            Newly constructed file.
        """

        value_map = {
            'id': data['id'],
            'mod': mod,
            'name': data['file_name_on_disk'],
            'date': parse_date(data['file_date']),
            'release': Release[data['release_type']],
            'url': data['download_url'],
            'dependencies': [
                d['add_on_id'] for d in data['dependencies']
                if d['type'].lower() == 'required'
            ],
        }

        return cls(**value_map)

    @classmethod
    def from_yaml(cls: Type['File'], data: Mapping) -> 'File':
        """Re-construct the File from YAML.

        Keyword arguments:
            data: Interpreted YAML data.

        Returns:
            New instance of File corresponding to input data.
        """

        # Load mod part
        mod = Mod(id=data['id'], name=data['name'], summary=data['summary'])

        # Load file part
        value_map = dict(mod=mod, **(data['file']))

        return cls(**value_map)

    @classmethod
    def to_yaml(cls: Type['File'], instance: 'File') -> Mapping:
        """Represent the instance as YAML node.

        Keyword arguments:
            instance: The File to be represented.

        Returns:
            YAML representation of the instance.
        """

        # Dump mod part
        columns = (str(c).split('.')[-1] for c in Mod.__table__.columns)
        yml = {f: getattr(instance.mod, f) for f in columns}

        # Dump the file part
        yml['file'] = attr.asdict(instance)
        for field in ('mod',):
            del yml['file'][field]

        return yml
