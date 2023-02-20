"""Database objects. Represent databases of the Postgres cluster."""
from typing import TYPE_CHECKING, Any, Dict, Optional, Union
from ..sql import SQL, Composable, Identifier, Literal
from ..errors import *
from .. import util
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class Database(generic._DynamicObject, generic._CollectionChild):
    """
    Postgres Database object. Represents a database object on a Postgres server.

    Args:
        cluster (str): Postgres cluster object
        name (str): name of the database
        owner (str): Database owner
        encoding (str): Database encoding
        collation (str): Database collation
        is_template (bool): True if the database is a template
        oid (int): Database OID
        parent (DatabaseCollection): parent collection

    Attributes:
        name (str): Database name
        owner (str): Database owner
        encoding (str): Database encoding
        collation (str): Database collation
        character_type (str): Database character type
        is_template (bool): True if the database is a template
        allow_connections (bool): True if the database accepts connections
        connection_limit (int): Database connection limit
        last_sys_oid (int): Last system object ID
        frozen_xid (str): Frozen transaction ID
        min_multixact_id (str): Minimum multi-transaction ID
        tablespace (str): Default tablespace
        acl (str): Database access list
        oid (int): Database OID
    """

    def __init__(
        self,
        name: str,
        cluster: "Cluster" = None,
        parent: "DatabaseCollection" = None,
        owner: str = None,
        encoding: str = None,
        collation: str = None,
        is_template: bool = False,
        oid: Optional[int] = None,
        from_template: str = None,
    ):
        super().__init__(cluster=cluster, name=name, kind="DATABASE", oid=oid)
        generic._CollectionChild.__init__(self, parent=parent)
        self._owner = owner
        self._encoding = encoding
        self._collation = collation
        self._is_template = is_template
        self._from_template = from_template
        self._character_type: Optional[str] = None
        self._allow_connections = True
        self._connection_limit: Optional[int] = None
        self._last_sys_oid: Optional[int] = None
        self._frozen_xid: Optional[int] = None
        self._min_multixact_id: Optional[int] = None
        self._tablespace: Optional[str] = None
        self._acl: Optional[str] = None

    def _modify(self, column: str, value: Any):
        """Internal pg_database modification function"""

        sql = SQL("UPDATE pg_catalog.pg_database SET {column} = {value} WHERE datname = %s").format(
            column=Identifier(column), value=Literal(value)
        )
        self.cluster.execute(sql, self.name)

    # properties
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        generic._set_ephemeral_attr(self, "name", name)

    @property
    def owner(self) -> Optional[str]:
        return self._owner

    @owner.setter
    def owner(self, owner: str):
        generic._set_ephemeral_attr(self, "owner", owner)

    @property
    def encoding(self) -> Optional[str]:
        return self._encoding

    @property
    def collation(self) -> Optional[str]:
        return self._collation

    @property
    def character_type(self) -> Optional[str]:
        return self._character_type

    @property
    def is_template(self) -> bool:
        return self._is_template

    @is_template.setter
    def is_template(self, value: bool):
        if not isinstance(value, bool):
            raise ValueError("Expected a boolean value")
        if self._is_template != value:
            keyword = "TRUE" if value else "FALSE"
            self._changes["is_template"] = generic._SQLChange(
                obj=self, sql=SQL(f"ALTER DATABASE {{fqn}} IS_TEMPLATE {keyword}").format(fqn=self._sql_fqn())
            )
            self._is_template = value

    @property
    def allow_connections(self) -> bool:
        return self._allow_connections

    @property
    def connection_limit(self) -> Optional[int]:
        return self._connection_limit

    @connection_limit.setter
    def connection_limit(self, value: int):
        if self._connection_limit != value:
            self._changes["connection_limit"] = generic._SQLChange(
                obj=self,
                sql=SQL("ALTER DATABASE {fqn} CONNECTION LIMIT {value}").format(
                    fqn=self._sql_fqn(), value=Literal(value)
                ),
            )
            self._connection_limit = value

    @property
    def last_sys_oid(self) -> Optional[int]:
        return self._last_sys_oid

    @property
    def frozen_xid(self) -> Optional[int]:
        return self._frozen_xid

    @property
    def min_multixact_id(self) -> Optional[int]:
        return self._min_multixact_id

    @property
    def tablespace(self) -> Optional[str]:
        return self._tablespace

    @tablespace.setter
    def tablespace(self, value: str):
        generic._set_ephemeral_attr(self, "tablespace", value)

    @property
    def acl(self) -> Optional[str]:
        return self._acl

    # methods
    def drop(self, terminate_connections: bool = False):
        """Drops the database represented by this object

        Args:
            terminate_connections (bool): Force all connections to be terminated after disabling the database
        """
        try:
            if terminate_connections:
                self.disable()
                self.cluster.terminate(databases=[self.name])
            self.cluster.execute(SQL("DROP DATABASE {database};").format(database=self._sql_fqn()))
        except:
            if terminate_connections:
                self.enable()
            raise

    def refresh(self):
        """Re-initializes the object, refreshing its properties"""
        super().refresh()
        self._from_template = None
        if not self._ephemeral:
            sql = util.get_sql("get_database") + SQL(" WHERE d.oid = %s")
            result = self.cluster.execute(sql, self.oid)
            if not result:
                raise PostgresError("Database not found")
            mapper = _DatabaseMapper(result[0])
            mapper.map(self)

    def disable(self, terminate_connections: bool = False):
        """Disallows connections to a database by modifying pg_database.datallowconn.

        Args:
            terminate_connections (bool): Force all connections to be dropped after disabling the database
        """
        self._modify(column="datallowconn", value=False)
        if terminate_connections:
            self.cluster.terminate(databases=[self.name])

    def enable(self):
        """Enables connections to a database by modifying pg_database.datallowconn"""
        self._modify(column="datallowconn", value=True)

    def create(self):
        """Create a database on the Postgres cluster"""
        self.cluster.execute(self.script(as_composable=True))
        sql = util.get_sql("get_database") + SQL(" WHERE datname = %s")
        _DatabaseMapper(self.cluster.execute(sql, self.name)[0]).map(self)

    def script(self, as_composable: bool = False) -> Union[str, Composable]:
        """Generate a database creation script.

        Args:
            as_composable (bool): return Composable object instead of plain text

        Returns:
            Union[str, Composable]: database creation script
        """
        sql = "CREATE DATABASE {db}"
        params: Dict[str, Composable] = {"db": self._sql_fqn()}
        if self._from_template:
            sql += " TEMPLATE {template}"
            params["template"] = Identifier(self._from_template)
        if self.owner:
            sql += " OWNER {owner}"
            params["owner"] = Identifier(self.owner)
        if self.encoding:
            sql += " ENCODING {encoding}"
            params["encoding"] = Literal(self.encoding)
        if self.collation:
            sql += " LC_COLLATE {locale} LC_CTYPE {locale}"
            params["locale"] = Literal(self.collation)
        if self.is_template:
            sql += " IS_TEMPLATE"

        command = SQL(sql).format(**params)
        if as_composable:
            return command
        else:
            with self.cluster.adapter.cursor() as cur:
                return cur.mogrify(command)


class _DatabaseMapper(generic._BaseObjectMapper[Database]):
    """Maps out a resultset from a database query to a database object"""

    attributes = [
        "name",
        "owner",
        "encoding",
        "collation",
        "character_type",
        "is_template",
        "allow_connections",
        "connection_limit",
        "last_sys_oid",
        "frozen_xid",
        "min_multixact_id",
        "tablespace",
        "acl",
        "oid",
    ]


class DatabaseCollection(generic._BaseCollection[Database]):
    """An iterable collection of databases indexed by database name."""

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and retrieves child objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_database")
        result = self.cluster.execute(sql)
        for mapper in [_DatabaseMapper(x) for x in result]:
            self[mapper["name"]] = mapper.map(
                Database(cluster=self.cluster, name=mapper["name"], parent=self, oid=mapper["oid"])
            )

    def new(
        self,
        name: str,
        template: str = None,
        owner: str = None,
        is_template: bool = False,
        encoding: str = None,
        collation: str = None,
    ) -> Database:
        """Create a database object on the current Postgres cluster. The object
        is created ephemeral and either needs to be added to the database collection,
        or .create() needs to be executed.

        Args:
            name (str): The name of the database
            template (str): Name of the template database to use
            owner (str): Owner of the database
            encoding (str): Database encoding
            collation (str): Sets LC_COLLATE and LC_CTYPE for the database
            is_template (bool): whether the database is a template
        """
        return Database(
            cluster=self.cluster,
            name=name,
            parent=self,
            from_template=template,
            owner=owner,
            encoding=encoding,
            collation=collation,
            is_template=is_template,
        )

    def add(self, database: Database):
        """Adds the database object to the collection, simultaneously creating it on the cluster

        Args:
            database (Database): initialized database object
        """

        database.cluster = self.cluster
        database._parent = self
        database.create()
        self[database.name] = database
