"""Postgresql view objects"""
from typing import TYPE_CHECKING, Optional
from ..sql import SQL
from ..errors import *
from .. import util
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class View(generic._DynamicObject, generic._CollectionChild):
    """Postgres View object. Represents a view object on a Postgres server.

    Args:
        name (str): name of the view
        cluster (str): Postgres cluster object
        schema (str): schema name
        owner (str): view owner
        oid (int): view OID
        parent (ViewCollection): parent collection

    Attributes:
        name (str): View name
        cluster (str): Postgres cluster object
        schema (str): schema name
        owner (str): view owner
        oid (int): view OID
    """

    def __init__(
        self,
        name: str,
        schema: str = "public",
        owner: str = None,
        cluster: "Cluster" = None,
        parent: "ViewCollection" = None,
        oid: Optional[int] = None,
    ):
        """Initialize a new View object"""
        super().__init__(kind="VIEW", cluster=cluster, oid=oid, name=name, schema=schema)
        generic._CollectionChild.__init__(self, parent=parent)
        self._schema: str = schema
        self._owner = owner

    def drop(self, cascade: bool = False):
        """Drops the view from the Postgres cluster

        Args:
            cascade (bool): drop dependent objects
        """
        sql = SQL("DROP VIEW {view}").format(view=self._sql_fqn())
        if cascade:
            sql += SQL(" CASCADE")
        self.cluster.execute(sql)

    def refresh(self):
        """Re-initializes the object, refreshing its properties"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_view") + SQL(" WHERE c.oid = %s")
            result = self.cluster.execute(sql, (self.oid,))
            if not result:
                raise PostgresError("View with oid %s was not found", self.oid)
            mapper = _ViewMapper(result[0])
            mapper.map(self)

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


class _ViewMapper(generic._BaseObjectMapper[View]):
    """Maps out a resultset from a database query to a table object"""

    attributes = [
        "name",
        "owner",
        "schema",
        "oid",
    ]


class ViewCollection(generic._BaseCollection[View]):
    """An iterable collection of views indexed by view name.
    For views outside of the 'public' schema, index becomes "schemaname.tablename".
    """

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and refreshes the list of child objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_view")
        result = self.cluster.execute(sql)
        for mapper in [_ViewMapper(x) for x in result]:
            self[self._index(name=mapper["name"], schema=mapper["schema"])] = mapper.map(
                View(
                    cluster=self.cluster,
                    name=mapper["name"],
                    schema=mapper["schema"],
                    parent=self,
                    oid=mapper["oid"],
                )
            )
