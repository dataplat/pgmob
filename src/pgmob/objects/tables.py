"""Postgresql table objects"""
from typing import TYPE_CHECKING, Optional
from ..sql import SQL, Identifier
from ..errors import *
from .. import util
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class Table(generic._DynamicObject, generic._CollectionChild):
    """Postgres Table object. Represents a table object on a Postgres server.

    Args:
        name (str): table name
        cluster (str): Postgres cluster object
        schema (str): schema name
        owner (str): table owner
        oid (int): table OID
        parent (TableCollection): parent collection

    Attributes:
        name (str): Table name
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Table owner
        tablespace (str): Tablespace
        row_security (bool): Whether the row security is enabled
        oid (int): Table OID
    """

    def __init__(
        self,
        name: str,
        schema: str = "public",
        owner: str = None,
        cluster: "Cluster" = None,
        parent: "TableCollection" = None,
        oid: Optional[int] = None,
    ):
        """Initialize a new Table object"""
        super().__init__(kind="TABLE", cluster=cluster, oid=oid, name=name, schema=schema)
        generic._CollectionChild.__init__(self, parent=parent)
        self._schema: str = schema
        self._owner = owner
        self._tablespace: Optional[str] = None
        self._row_security: bool = False

    def drop(self, cascade: bool = False):
        """Drops the table from the Postgres cluster

        Args:
            cascade (bool): drop dependent objects
        """
        sql = SQL("DROP TABLE {table}").format(table=self._sql_fqn())
        if cascade:
            sql += SQL(" CASCADE")
        self.cluster.execute(sql)

    def refresh(self):
        """Re-initializes the object, refreshing its properties from Postgres cluster"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_table") + SQL(" WHERE c.oid = %s")
            result = self.cluster.execute(sql, (self.oid,))
            if not result:
                raise PostgresError("Table with oid %s was not found", self.oid)
            mapper = _TableMapper(result[0])
            mapper.map(self)

    @property
    def tablespace(self):
        return self._tablespace

    @tablespace.setter
    def tablespace(self, value: str):
        if self._tablespace != value:
            self._changes["tablespace"] = generic._SQLChange(
                obj=self,
                sql=SQL("ALTER TABLE {fqn} SET TABLESPACE {tablespace}").format(
                    fqn=self._sql_fqn(), tablespace=Identifier(value)
                ),
            )
            self._tablespace = value

    @property
    def row_security(self):
        return self._row_security

    @row_security.setter
    def row_security(self, value: bool):
        if self._row_security != value:
            keyword = "ENABLE" if value else "DISABLE"
            self._changes["row_security"] = generic._SQLChange(
                obj=self,
                sql=SQL(f"ALTER TABLE {{fqn}} {keyword} ROW LEVEL SECURITY").format(fqn=self._sql_fqn()),
            )
            self._row_security = value

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


class _TableMapper(generic._BaseObjectMapper[Table]):
    """Maps out a resultset from a database query to a table object"""

    attributes = [
        "name",
        "owner",
        "schema",
        "tablespace",
        "row_security",
        "oid",
    ]


class TableCollection(generic._BaseCollection[Table]):
    """An iterable collection of tables indexed by table name.
    For tables outside of the 'public' schema, index becomes "schemaname.tablename".
    """

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and refreshes the list of child objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_table")
        result = self.cluster.execute(sql)
        for mapper in [_TableMapper(x) for x in result]:
            self[self._index(name=mapper["name"], schema=mapper["schema"])] = mapper.map(
                Table(
                    cluster=self.cluster,
                    name=mapper["name"],
                    schema=mapper["schema"],
                    parent=self,
                    oid=mapper["oid"],
                )
            )
