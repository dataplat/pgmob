"""Postgresql table objects"""
from typing import TYPE_CHECKING, Any, Optional
from ..sql import SQL, Identifier, Literal
from ..errors import *
from .. import util
from .._decorators import get_lazy_property
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

    @property
    def columns(self) -> "ColumnCollection":
        """Table column collection

        Example:
            Retrieving tables from the server after refreshing table objects

            >>> cluster.execute("CREATE TABLE tab1(a int)")
            []
            >>> cluster.tables.refresh()
            >>> cluster.tables['tab1'].columns
            ColumnCollection('a')
            >>> cluster.tables['tab1'].columns['a'].type
            'integer'
        """
        return get_lazy_property(self, "columns", lambda: ColumnCollection(table=self, cluster=self.cluster))


def _set_column_attr(obj: "Column", attr: str, value: Any):
    params = dict(
        table=obj.table._sql_fqn(),
        name=obj._sql_fqn(),
        value=Identifier(value),
    )
    stmt_map = {
        "name": SQL("ALTER TABLE {table} RENAME COLUMN {name} TO {value}").format(**params),
        "stat_target": SQL("ALTER TABLE {table} ALTER COLUMN {name} SET STATISTICS {stats}").format(
            stats=Literal(value), **params
        ),
        "nullable": SQL(
            f"ALTER TABLE {{table}} ALTER COLUMN {{name}} {'SET' if not value else 'DROP'} NOT NULL"
        ).format(**params),
    }
    if getattr(obj, f"_{attr}") != value:
        obj._changes[attr] = generic._SQLChange(obj=obj, sql=stmt_map[attr])
        setattr(obj, f"_{attr}", value)


class Identity(generic.AliasEnum):
    """Postgres generated identity options
    https://www.postgresql.org/docs/current/sql-createtable.html
    """

    ALWAYS = "a"
    DEFAULT = "d"
    NOT_GENERATED = ""


class GeneratedColumn(generic.AliasEnum):
    """Postgres generated column options
    https://www.postgresql.org/docs/current/sql-createtable.html
    """

    STORED = "s"
    NOT_GENERATED = ""


class Column(generic._DynamicObject, generic._CollectionChild):
    """Postgres Column object. Represents a column object on a Postgres server.

    Args:
        name (str): column name
        cluster (str): Postgres cluster object
        parent (ColumnCollection): parent collection


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
        table: Table,
        type: str,
        cluster: "Cluster" = None,
        parent: "ColumnCollection" = None,
        stat_target: int = -1,
        number: int = None,
        is_array: bool = False,
        type_mod: int = None,
        nullable: bool = True,
        has_default: bool = False,
        identity: Identity = Identity.NOT_GENERATED,
        generated: GeneratedColumn = GeneratedColumn.NOT_GENERATED,
        collation: str = None,
        expression: str = None,
    ):
        super().__init__(kind="COLUMN", cluster=cluster, name=name)
        generic._CollectionChild.__init__(self, parent=parent)
        self.table = table
        self._type = type
        self._stat_target = stat_target
        self._number = number
        self._is_array = is_array
        self._type_mod = type_mod
        self._nullable = nullable
        self._has_default = has_default
        self._identity = Identity(identity)
        self._generated = GeneratedColumn(generated)
        self._collation = collation
        self._expression = expression

    @property
    def _ephemeral(self) -> bool:
        return self._number is None

    def refresh(self):
        """Re-initializes the object, refreshing its properties from Postgres cluster"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_column") + SQL(" AND a.attnum = %s")
            result = self.cluster.execute(sql, (self.table.oid, self.number))
            if not result:
                raise PostgresError("Column number %s was not found", self.number)
            mapper = _ColumnMapper(result[0])
            mapper.map(self)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        _set_column_attr(self, "name", name)

    @property
    def type(self) -> str:
        return self._type

    @property
    def stat_target(self) -> int:
        return self._stat_target

    @stat_target.setter
    def stat_target(self, value: int):
        _set_column_attr(self, "stat_target", value)

    @property
    def number(self) -> Optional[int]:
        return self._number

    @property
    def is_array(self) -> bool:
        return self._is_array

    @property
    def type_mod(self) -> Optional[int]:
        return self._type_mod

    @property
    def nullable(self) -> bool:
        return self._nullable

    @nullable.setter
    def nullable(self, value: bool):
        _set_column_attr(self, "nullable", value)

    @property
    def has_default(self) -> bool:
        return self._has_default

    @property
    def identity(self) -> Identity:
        return self._identity

    @property
    def generated(self) -> GeneratedColumn:
        return self._generated

    @property
    def collation(self) -> Optional[str]:
        return self._collation

    @property
    def expression(self) -> Optional[str]:
        return self._expression

    def set_type(self, type: str, collation: Optional[str] = None, using: Optional[str] = None) -> None:
        """Changes the column type.

        Args:
            type (str): new type name
            collation (Optional[str]): Collation name for the type, if needed
            using (Optional[str]): USING clause specifying how to compute the new column value from the old

        Returns:
            None
        """
        params = dict(
            table=self.table._sql_fqn(),
            name=self._sql_fqn(),
        )
        sql = (
            SQL(f"ALTER TABLE {{table}} ALTER COLUMN {{name}} TYPE {type}").format(**params)
            + (SQL(" COLLATE {collation}").format(collation=Identifier(collation)) if collation else SQL(""))
            + SQL(f" USING ({using})" if using else "")
        )
        self.cluster.execute(sql)
        self.refresh()

    def drop(self, cascade: bool = False):
        """Drops the column from an existing table

        Args:
            cascade (bool): drop dependent objects
        """
        sql = SQL("ALTER TABLE {table} DROP COLUMN {name}").format(
            table=self.table._sql_fqn(),
            name=self._sql_fqn(),
        )
        if cascade:
            sql += SQL(" CASCADE")
        self.cluster.execute(sql)


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


class _ColumnMapper(generic._BaseObjectMapper[Column]):
    """Maps out a resultset from a database query to a column object"""

    attributes = [
        "name",
        "type",
        "stat_target",
        "number",
        "is_array",
        "type_mod",
        "nullable",
        "has_default",
        "identity",
        "generated",
        "collation",
        "expression",
    ]

    exclude = ["identity", "generated"]

    def map(self, obj: Column) -> Column:
        """Assigns attributes to the Postgres column based on
        the definition resultset and returns the object.

        Args:
            obj (Column): Postgres column object
        """
        super().map(obj)
        obj._identity = Identity(self["identity"])
        obj._generated = GeneratedColumn(self["generated"])
        return obj


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


class ColumnCollection(generic._BaseCollection[Column]):
    """An iterable collection of columns indexed by column name."""

    def __init__(self, cluster: "Cluster", table: "Table"):
        super().__init__(cluster=cluster, sorted=False)
        self.table = table
        if table and cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and refreshes the list of child objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_column") + SQL(" ORDER BY a.attnum")
        result = self.cluster.execute(sql, self.table.oid)
        for mapper in [_ColumnMapper(x) for x in result]:
            self[mapper["name"]] = mapper.map(
                Column(
                    name=mapper["name"],
                    parent=self,
                    table=self.table,
                    type=mapper["type"],
                )
            )
