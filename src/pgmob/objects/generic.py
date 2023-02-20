"""Internal generic objects shared between other objects."""

from abc import abstractmethod
from enum import Enum
import re
from typing import Any, Dict, Generic, Iterator, List, Optional, TYPE_CHECKING, Tuple, TypeVar
from pgmob import errors
from pgmob._decorators import deprecated
from pgmob.sql import SQL, Identifier, Composable

if TYPE_CHECKING:
    from ..cluster import Cluster


T = TypeVar("T")


class _BasePostgresObject(object):
    """Base class for any Postgres object with oid.

    Args:
        oid (Optional[int]): object id

    Attributes:
        oid (Optional[int]): object id
    """

    def __init__(self, oid: Optional[int] = None):
        self._oid = oid

    # properties
    @property
    def oid(self) -> Optional[int]:
        return self._oid

    @oid.setter
    def oid(self, value: int):
        if not self._ephemeral:
            raise errors.PostgresError("The object is not ephemeral. Can't set oid.")
        self._oid = value

    @property
    def _ephemeral(self) -> bool:
        return self._oid is None or self._oid <= 0


class _BaseObjectMapper(Generic[T]):
    """Maps the resultset to a Dynamic Object"""

    attributes: List[str] = []
    exclude: List[str] = []

    def __init__(self, definition: tuple):
        self.definition = definition

    def __getitem__(self, key: str) -> object:
        return self.definition[self.attributes.index(key)]

    def map(self, obj: T) -> T:
        """Assigns attributes to the Postgres object based on the definition resultset
        and returns the object.

        Args:
            obj (_BasePostgresObject): Postgres object
        """
        for i in range(len(self.attributes)):
            if self.attributes[i] not in self.exclude:
                setattr(obj, f"_{self.attributes[i]}", self.definition[i])

        return obj


class _ClusterBound(object):
    """Object that is attached to a Cluster. Implements cluster retrieval internal function"""

    def __init__(self, cluster: "Cluster" = None):
        self._cluster = cluster

    @property
    def cluster(self) -> "Cluster":
        """Retrieves the Cluster instance bound to the object

        Returns:
            Cluster: Postgres cluster object
        """
        if not self._cluster:
            raise errors.PostgresError("Object is not associated with a cluster")
        return self._cluster

    @cluster.setter
    def cluster(self, value: "Cluster"):
        """Bounds object to a cluster

        Args:
            value (Cluster): Postgres cluster object
        """
        from ..cluster import Cluster

        if value is not None and not isinstance(value, Cluster):
            raise ValueError("%s is not a cluster object", value.__class__)
        self._cluster = value


class Fqn(object):
    """Fully qualified object name. Defined by schema name (optional) and object name.

    Args:
        name (str): object name
        schema (Optional[str]): schema name
    """

    def __init__(self, name: str, schema: Optional[str] = None):
        self.name = name
        self.schema = schema

    def get_identifier(self) -> Composable:
        """Returns a prepared identifier or set of identifiers to insert into the query

        Returns:
            Composable: object identifier
        """
        result: Composable = Identifier(self.name)
        if self.schema:
            result = SQL(".").join([Identifier(self.schema), result])
        return result


class _FqnObject(_BasePostgresObject, _ClusterBound):
    """Base Postgres object that has FQN, bound to a cluster and supports ephemeral changes"""

    def __init__(
        self,
        kind: str,
        name: str,
        oid: Optional[int] = None,
        schema: Optional[str] = None,
        cluster: "Cluster" = None,
    ):
        _BasePostgresObject.__init__(self, oid=oid)
        _ClusterBound.__init__(self, cluster=cluster)
        self._fqn = Fqn(name=name, schema=schema)
        self._name = name
        self._schema = schema
        self._kind = kind

    @property
    def name(self):
        return self._name

    @property
    def schema(self):
        return self._schema

    @property
    def kind(self) -> str:
        return self._kind

    def __repr__(self):
        name = (f"{self.schema}." if self.schema and self.schema != "public" else "") + self.name
        return f"{self.__class__.__name__}('{name}')"

    def _sql_fqn(self) -> Composable:
        return self._fqn.get_identifier()


class _DynamicObject(_FqnObject):
    """Object that supports ephemeral changes. Should be inherited by objects
    that support property change with an eventual .alter() call.
    """

    def __init__(
        self,
        kind: str,
        name: str,
        oid: Optional[int] = None,
        schema: Optional[str] = None,
        cluster: "Cluster" = None,
    ):
        super().__init__(kind=kind, name=name, schema=schema, cluster=cluster, oid=oid)
        self._changes = _ChangeCollection()

    def alter(self):
        """Alters remote object by applying local changes that were queued up for the object"""
        keys = list(self._changes.keys())
        # ensure that alter name is queued up last
        for key in [k for k in keys if k != "name"] + (["name"] if "name" in keys else []):
            self._changes[key].apply()
            self._changes.pop(key)
        self.refresh()

    def refresh(self):
        """Re-initializes the object, refreshing its properties"""
        self._changes = _ChangeCollection()


def _set_ephemeral_attr(obj: _DynamicObject, attr: str, value: Any):
    params = dict(
        fqn=obj._sql_fqn(),
        value=Identifier(value),
    )
    stmt_map = dict(
        owner=SQL(f"ALTER {obj._kind} {{fqn}} OWNER TO {{value}}").format(**params),
        name=SQL(f"ALTER {obj._kind} {{fqn}} RENAME TO {{value}}").format(**params),
        schema=SQL(f"ALTER {obj.kind} {{fqn}} SET SCHEMA {{value}}").format(**params),
        tablespace=SQL(f"ALTER {obj.kind} {{fqn}} SET TABLESPACE {{value}}").format(**params),
    )

    if getattr(obj, f"_{attr}") != value:
        obj._changes[attr] = _SQLChange(obj=obj, sql=stmt_map[attr])
        setattr(obj, f"_{attr}", value)


class MappedCollection(Dict[str, T]):
    """Class implements an iterable dictionary.
    Items are accessed via a key, but when iterated over, acts as a list."""

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        for key in self.keys():
            yield self[key]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.keys()})"


class SortedMappedCollection(Dict[str, T]):
    """Class implements an iterable sorted dictionary.
    Items are accessed via a key, but when iterated over, acts as a sorted list."""

    def __iter__(self) -> Iterator[T]:  # type: ignore[override]
        for key in sorted(self.keys()):
            yield self[key]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({sorted(self.keys())})"


class _BaseCollection(_ClusterBound, SortedMappedCollection[T]):
    """Generic Postgres collection object bound to a cluster."""

    def __init__(self, cluster: "Cluster"):
        SortedMappedCollection.__init__(self)  # type: ignore
        _ClusterBound.__init__(self, cluster=cluster)

    def __setitem__(self, key: str, value: T):
        if not isinstance(value, _ClusterBound):
            raise AttributeError("Unsupported type %s", type(value))
        value.cluster = self.cluster
        SortedMappedCollection.__setitem__(self, key, value)  # type: ignore

    @staticmethod
    def _index(name: str, schema: str):
        """Returns index provided the fqn names"""
        return name if schema == "public" else f"{schema}.{name}"

    def refresh(self):
        """Implements collection refresh, resetting all pending changes and refreshing members.
        Should have an implementation in child classes to load members."""
        self.clear()

    # TODO: implement methods in each child class
    # @abstractmethod
    # def add(self, item: T):
    #     """Abstract method that should be overloaded by each inheriting class that wants to implement add"""
    #     raise NotImplementedError()

    # @abstractmethod
    # def new(self, item: T):
    #     """Abstract method that should be overloaded by each inheriting class that wants to implement new"""
    #     raise NotImplementedError()


class _CollectionChild(object):
    """Defines an object belonging to a Postgres collection"""

    def __init__(self, parent: _BaseCollection = None):
        self._parent = parent

    @property
    def parent(self) -> Optional[_BaseCollection]:
        return self._parent


class _ObjectChange(object):
    def __init__(self, obj: _DynamicObject, task, *args, **kwargs):
        if not isinstance(obj, _DynamicObject):
            raise AttributeError("This object class is not supported")
        self.task = task
        self.object = obj
        self.args = args
        self.kwargs = kwargs

    def apply(self):
        """Applies the change"""
        self.task(*self.args, **self.kwargs)


class _SQLChange(_ObjectChange):
    def __init__(self, obj: _DynamicObject, sql: Composable, params: tuple = None):
        def task():
            obj.cluster.execute(sql, params)

        _ObjectChange.__init__(self, task=task, obj=obj)
        self.sql = sql
        self.params = params


class _ChangeCollection(MappedCollection[_ObjectChange]):
    """An iterable collection of changes indexed by attribute name."""

    def __setitem__(self, key, value):
        if not isinstance(value, _ObjectChange):
            raise AttributeError(f"{value.__class__.__name__} is not of an _ObjectChange type")
        MappedCollection.__setitem__(self, key, value)


class AliasEnum(Enum):
    def __repr__(self):
        return f"{self.__class__.__name__}.{self.name}"

    def __str__(self):
        return self.name
