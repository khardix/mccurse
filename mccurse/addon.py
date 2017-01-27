"""Objects storing data or information related to add-ons
   (i.e. Mod, mod's File, etc.).
"""

from datetime import datetime
from typing import Mapping, Sequence
from weakref import WeakValueDictionary

import attr
from attr import validators as vld
from sqlalchemy import Column, Integer, String
from sqlalchemy import or_, bindparam
from sqlalchemy.ext.baked import bakery
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.session import Session as SQLSession

# Used exceptions -- make them available in current namespace
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound  # noqa: F401

from .proxy import Release

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

        return query(connection).params(name='%{}%'.format(name)).one()


@attr.s(slots=True, hash=False)
class File:
    """Metadata of a file belonging to some mod."""

    #: Cache of existing instances
    cache = WeakValueDictionary()
    # Enable weak references
    __weakref__ = attr.ib(init=False, hash=False, cmp=False, repr=False)

    #: File identification
    id = attr.ib(validator=vld.instance_of(int))
    #: Associated mod identification
    mod_id = attr.ib(validator=vld.instance_of(int))
    #: File system base name
    name = attr.ib(validator=vld.instance_of(str))
    #: Publication date
    date = attr.ib(validator=vld.instance_of(datetime))
    #: Release type
    release = attr.ib(validator=vld.instance_of(Release))
    #: Remote URL for download
    url = attr.ib(validator=vld.instance_of(str))
    #: Dependencies; {mod_id: File}
    dependencies = attr.ib(
        validator=vld.optional(vld.instance_of(dict)),
        default=attr.Factory(dict),
    )

    def __attrs_post_init__(self):
        """Register instance in the cache after successful initialization."""

        self.__class__.cache[self.mod_id] = self
