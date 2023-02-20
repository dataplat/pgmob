"""Schema objects. Represents schemas on the Postgres cluster"""
from typing import TYPE_CHECKING, Any, Dict, Optional, Union
from ..sql import SQL, Composable, Identifier
from ..errors import *
from .. import util
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class Schema(generic._DynamicObject, generic._CollectionChild):
    """Postgres schema object. Represents a schema object on a Postgres cluster.

    Args:
        name (str): schema name
        owner (str): schema owner
        oid (int): Schema OID
        cluster (str): Postgres cluster object
        parent (SchemaCollection): parent collection

    Attributes:
        name (str): Schema name
        cluster (str): Postgres cluster object
        owner (str): Schema owner
        oid (int): Schema OID
    """

    def __init__(
        self,
        name: str,
        owner: str = None,
        cluster: "Cluster" = None,
        parent: "SchemaCollection" = None,
        oid: Optional[int] = None,
    ):
        super().__init__(cluster=cluster, name=name, kind="SCHEMA", oid=oid)
        generic._CollectionChild.__init__(self, parent=parent)
        self._owner = owner

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

    def drop(self, cascade: bool = False):
        """Drops the schema from the Postgres cluster

        Args:
            cascade (bool): drop dependent objects
        """

        sql = SQL("DROP SCHEMA {schema}").format(schema=self._sql_fqn())
        if cascade:
            sql += SQL(" CASCADE")
        self.cluster.execute(sql)

    def refresh(self):
        """Re-initializes the object, refreshing its properties"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_schema") + SQL(" WHERE n.oid = %s")
            result = self.cluster.execute(sql, (self.oid,))
            if not result:
                raise PostgresError("Schema %s with oid %s was not found", self.name, self.oid)
            mapper = _SchemaMapper(result[0])
            mapper.map(self)

    def create(self):
        """Create a database on the Postgres cluster"""
        self.cluster.execute(self.script(as_composable=True))
        sql = util.get_sql("get_schema") + SQL(" WHERE n.nspname = %s")
        _SchemaMapper(self.cluster.execute(sql, self.name)[0]).map(self)

    def script(self, as_composable: bool = False) -> Union[str, Composable]:
        """Generate a schema creation script.

        Args:
            as_composable (bool): return Composable object instead of plain text

        Returns:
            Union[str, Composable]: schema creation script
        """
        sql = "CREATE SCHEMA {schema}"
        params: Dict[str, Composable] = {"schema": self._sql_fqn()}
        if self.owner:
            sql += " AUTHORIZATION {owner}"
            params["owner"] = Identifier(self.owner)

        command = SQL(sql).format(**params)
        if as_composable:
            return command
        else:
            with self.cluster.adapter.cursor() as cur:
                return cur.mogrify(command)


class _SchemaMapper(generic._BaseObjectMapper[Schema]):
    """Maps out a resultset from a database query to a schema object"""

    attributes = [
        "name",
        "owner",
        "oid",
    ]


class SchemaCollection(generic._BaseCollection[Schema]):
    """An iterable collection of schemas indexed by name."""

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and retrieves child objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_schema")
        result = self.cluster.execute(sql)
        for mapper in [_SchemaMapper(x) for x in result]:
            self[mapper["name"]] = mapper.map(Schema(cluster=self.cluster, name=mapper["name"], parent=self))

    def new(
        self,
        name: str,
        owner: str = None,
    ) -> Schema:
        """Create a schema object on the current Postgres cluster. The object
        is created ephemeral and either needs to be added to the schema collection,
        or .create() needs to be executed.

        Args:
            name (str): The name of the database
            owner (str): Owner of the database
        """
        return Schema(
            cluster=self.cluster,
            name=name,
            parent=self,
            owner=owner,
        )

    def add(self, schema: Schema):
        """Adds the schema object to the collection, simultaneously creating it on the cluster

        Args:
            schema (Schema): initialized schema object
        """
        schema.cluster = self.cluster
        schema._parent = self
        schema.create()
        self[schema.name] = schema
