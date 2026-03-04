"""Postgresql table objects"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors import PostgresError
from ..sql import SQL, Identifier
from . import generic
from .mixins import NamedObjectMixin, OwnedObjectMixin, SchemaObjectMixin, TablespaceObjectMixin

if TYPE_CHECKING:
    from ..cluster import Cluster
    from ..providers.base import MetadataProvider


class Table(
    NamedObjectMixin,
    OwnedObjectMixin,
    SchemaObjectMixin,
    TablespaceObjectMixin,
    generic._DynamicObject,
    generic._CollectionChild,
):
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
        owner (str): Table owner
        schema (str): Schema name
        tablespace (str): Tablespace
        cluster (str): Postgres cluster object
        row_security (bool): Whether the row security is enabled
        oid (int): Table OID
    """

    def __init__(
        self,
        name: str,
        schema: str = "public",
        owner: str | None = None,
        cluster: Cluster | None = None,
        parent: TableCollection | None = None,
        oid: int | None = None,
    ):
        """Initialize a new Table object"""
        super().__init__(kind="TABLE", cluster=cluster, oid=oid, name=name, schema=schema)
        generic._CollectionChild.__init__(self, parent=parent)

        # Initialize mixins
        self._init_name(name)
        self._init_owner(owner)
        self._init_schema(schema)
        self._init_tablespace(None)

        # Table-specific attributes
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
            if self.oid is None:
                raise PostgresError("Table has no OID; cannot refresh")
            data = self.cluster.metadata_provider.get_table(self.oid)
            if not data:
                raise PostgresError("Table with oid %s was not found", self.oid)
            mapper = _TableMapper(tuple(data.get(attr) for attr in _TableMapper.attributes))
            mapper.map(self)
            self._fqn.name = self._name
            self._fqn.schema = self._schema

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

    def __init__(self, cluster: Cluster):
        super().__init__(cluster=cluster)
        self.provider: MetadataProvider = cluster.metadata_provider
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and refreshes the list of child objects from the cluster"""
        super().refresh()
        for data in self.provider.get_tables():
            table = _TableMapper.from_dict(Table, data, cluster=self.cluster, parent=self)
            self[self._index(name=data["name"], schema=data["schema"])] = table

    def get_by_oid(self, oid: int) -> Table | None:
        """Retrieve a table by its OID using the metadata provider.

        Args:
            oid: The table's object identifier.

        Returns:
            Table object if found, None otherwise.
        """
        data = self.provider.get_table(oid)
        if not data:
            return None
        return _TableMapper.from_dict(Table, data, cluster=self.cluster, parent=self)
