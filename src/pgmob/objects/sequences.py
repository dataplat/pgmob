"""Sequence objects"""
from typing import TYPE_CHECKING, Optional
from ..sql import SQL, Literal
from ..errors import *
from .. import util
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class Sequence(generic._DynamicObject, generic._CollectionChild):
    """Postgres sequence object. Represents a sequence on a Postgres server.

    Args:
        name (str): name of the sequence
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Sequence owner
        oid (int): Sequence OID
        parent (SequenceCollection): parent collection

    Attributes:
        name (str): Sequence name
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Sequence owner
        data_type (str): Data type
        start_value (int): Sequence start value
        min_value (int): Sequence minimum value
        max_value (int): Sequence maximum value
        last_value (int): Sequence last value
        increment_by (int): Increment step
        cycle (bool): Whether the sequence is allowed to cycle
        cache_size (int): Cache size
        oid (int): Sequence OID
    """

    def __init__(
        self,
        name: str,
        schema: str = "public",
        owner: str = None,
        cluster: "Cluster" = None,
        parent: "SequenceCollection" = None,
        oid: Optional[int] = None,
    ):
        """Initialize a new Sequence object"""
        super().__init__(kind="SEQUENCE", cluster=cluster, oid=oid, name=name, schema=schema)
        generic._CollectionChild.__init__(self, parent=parent)
        self._owner = owner
        self._schema: str = schema
        self._data_type: Optional[str] = None
        self._start_value: Optional[int] = None
        self._min_value: Optional[int] = None
        self._max_value: Optional[int] = None
        self._increment_by: Optional[int] = None
        self._cycle: Optional[bool] = None
        self._cache_size: Optional[int] = None
        self._last_value: Optional[int] = None

    @property
    def data_type(self):
        return self._data_type

    @data_type.setter
    def data_type(self, value: str):
        if self._data_type != value:
            self._changes["data_type"] = generic._SQLChange(
                obj=self, sql=SQL(f"ALTER SEQUENCE {{fqn}} AS {value}").format(fqn=self._sql_fqn())
            )
            self._data_type = value

    @property
    def start_value(self) -> Optional[int]:
        return self._start_value

    @start_value.setter
    def start_value(self, value: int):
        if self._start_value != value:
            self._changes["start_value"] = generic._SQLChange(
                obj=self,
                sql=SQL("ALTER SEQUENCE {fqn} START WITH {value}").format(
                    fqn=self._sql_fqn(), value=Literal(value)
                ),
            )
            self._start_value = value

    @property
    def min_value(self) -> Optional[int]:
        return self._min_value

    @min_value.setter
    def min_value(self, value: int):
        if self._min_value != value:
            if value == None:
                sql = SQL("ALTER SEQUENCE {fqn} NO MINVALUE").format(fqn=self._sql_fqn())
            else:
                sql = SQL("ALTER SEQUENCE {fqn} MINVALUE {value}").format(
                    fqn=self._sql_fqn(), value=Literal(value)
                )
            self._changes["min_value"] = generic._SQLChange(obj=self, sql=sql)
            self._min_value = value

    @property
    def max_value(self) -> Optional[int]:
        return self._max_value

    @max_value.setter
    def max_value(self, value: int):
        if self._max_value != value:
            if value == None:
                sql = SQL("ALTER SEQUENCE {fqn} NO MAXVALUE").format(fqn=self._sql_fqn())
            else:
                sql = SQL("ALTER SEQUENCE {fqn} MAXVALUE {value}").format(
                    fqn=self._sql_fqn(), value=Literal(value)
                )
            self._changes["max_value"] = generic._SQLChange(obj=self, sql=sql)
            self._max_value = value

    @property
    def increment_by(self) -> Optional[int]:
        return self._increment_by

    @increment_by.setter
    def increment_by(self, value: int):
        if self._increment_by != value:
            self._changes["increment_by"] = generic._SQLChange(
                obj=self,
                sql=SQL("ALTER SEQUENCE {fqn} INCREMENT BY {value}").format(
                    fqn=self._sql_fqn(), value=Literal(value)
                ),
            )
            self._increment_by = value

    @property
    def cycle(self) -> Optional[bool]:
        return self._cycle

    @property
    def cache_size(self) -> Optional[int]:
        return self._cache_size

    @property
    def last_value(self) -> Optional[int]:
        return self._last_value

    @property
    def owner(self) -> Optional[str]:
        return self._owner

    @owner.setter
    def owner(self, owner: str):
        generic._set_ephemeral_attr(self, "owner", owner)

    @property
    def schema(self) -> str:
        return self._schema

    @schema.setter
    def schema(self, schema: str):
        generic._set_ephemeral_attr(self, "schema", schema)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        generic._set_ephemeral_attr(self, "name", name)

    # methods
    def drop(self, cascade: bool = False):
        """Drops the sequence from the Postgres cluster

        Args:
            cascade (bool): drop dependent objects
        """

        sql = SQL("DROP SEQUENCE {seq}").format(seq=self._sql_fqn())
        if cascade:
            sql += SQL(" CASCADE")
        self.cluster.execute(sql)

    def nextval(self):
        """Retrieve the next value from the sequence"""

        sql = SQL("SELECT nextval(%s)")
        return self.cluster.execute(sql, (self.oid))[0][0]

    def currval(self):
        """Retrieve the next value from the sequence"""

        sql = SQL("SELECT currval(%s)")
        return self.cluster.execute(sql, (self.oid))[0][0]

    def setval(self, value: int, is_called: bool = False):
        """Set sequence's current value and, optionally, is_called flag

        Args:
            is_called (bool): set is_called flag
        """
        if is_called:
            sql = SQL("SELECT setval(%s, %s, true)")
        else:
            sql = SQL("SELECT setval(%s, %s)")
        self.cluster.execute(sql, (self.oid, value))[0][0]

    def refresh(self):
        """Re-initializes the object, refreshing its properties from Postgres cluster"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_sequence") + SQL(" WHERE c.oid = %s")
            result = self.cluster.execute(sql, (self.oid,))
            if not result:
                raise PostgresError("Sequence with oid %s was not found", self.oid)
            mapper = _SequenceMapper(result[0])
            mapper.map(self)


class _SequenceMapper(generic._BaseObjectMapper[Sequence]):
    """Maps out a resultset from a database query to a sequence object"""

    attributes = [
        "name",
        "owner",
        "schema",
        "data_type",
        "start_value",
        "min_value",
        "max_value",
        "increment_by",
        "cycle",
        "cache_size",
        "last_value",
        "oid",
    ]


class SequenceCollection(generic._BaseCollection[Sequence]):
    """An iterable collection of sequences indexed by sequence name.
    For sequences outside of the 'public' schema, index becomes "schemaname.sequencename".
    """

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and refreshes the list of child objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_sequence")
        result = self.cluster.execute(sql)
        for mapper in [_SequenceMapper(x) for x in result]:
            self[self._index(name=mapper["name"], schema=mapper["schema"])] = mapper.map(
                Sequence(
                    cluster=self.cluster,
                    name=mapper["name"],
                    schema=mapper["schema"],
                    parent=self,
                    oid=mapper["oid"],
                )
            )

    # TODO: uncomment when .create() and .new() are implemented
    # def add(self, sequence: Sequence):
    #     """Adds the database object to the collection, simultaneously creating it on the cluster

    #     Args:
    #         database (Database): initialized database object
    #     """

    #     sequence.cluster = self.cluster
    #     sequence._parent = self
    #     sequence.create()
    #     self[self._index(name=sequence.name, schema=sequence.schema)] = sequence
