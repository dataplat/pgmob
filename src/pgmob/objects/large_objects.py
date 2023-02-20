"""Postgresql largeobject objects"""
from typing import TYPE_CHECKING, Optional
from pgmob.sql import SQL, Literal
from pgmob.adapters.base import BaseLargeObject
from pgmob.errors import *
from pgmob import util
from . import generic

if TYPE_CHECKING:
    from ..cluster import Cluster


class LargeObject(generic._DynamicObject, generic._CollectionChild):
    """
    Postgres LargeObject object. Represents a large object on a Postgres server.

    Args:
        oid (int): LargeObject OID
        cluster (str): Postgres cluster object
        definition (tuple): definition of the largeobject; used internally

    Attributes:
        oid (int): LargeObject OID
        cluster (str): Postgres cluster object
        owner (str): LargeObject owner
    """

    def __init__(
        self,
        oid: int = None,
        cluster: "Cluster" = None,
        parent: "LargeObjectCollection" = None,
        owner: str = None,
    ):
        """Initialize a new LargeObject object"""
        super().__init__(kind="LARGE OBJECT", cluster=cluster, oid=oid, name=str(oid))
        generic._CollectionChild.__init__(self, parent=parent)
        self._owner = owner

    def _sql_fqn(self) -> Literal:
        return Literal(self._oid)

    def _with_lobject(self, task, mode="rw"):
        cluster = self.cluster
        with cluster._no_autocommit():
            lo = cluster.adapter.lobject(self._oid, mode=mode)
            result = task(lo)
            lo.close()
            return result

    @property
    def owner(self) -> Optional[str]:
        return self._owner

    @owner.setter
    def owner(self, owner: str):
        generic._set_ephemeral_attr(self, "owner", owner)

    def drop(self):
        """Drops the largeobject from the Postgres cluster"""
        self._with_lobject(lambda lo: lo.unlink())

    def refresh(self):
        """Re-initializes the object, refreshing its properties"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_large_object") + SQL(" WHERE lo.oid = %s")
            result = self.cluster.execute(sql, (self._oid,))
            if not result:
                raise PostgresError("LargeObject not found")
            mapper = _LargeObjectMapper(result[0])
            mapper.map(self)

    def write(self, data: bytes, truncate: bool = True):
        """Overwrites Large object contents

        Args:
            data(bytes): Large Object contents
            truncate(bool): Whether to truncate the object before write. Default = True
        """

        def task(lob: BaseLargeObject):
            try:
                if truncate:
                    lob.truncate()
                lob.write(data)
            finally:
                lob.close()

        self._with_lobject(task, mode="w")

    def read(self, mode="t"):
        """Read Large object contents

        Args:
            mode(str):
                - r  Open for read only
                - w  Open for write only
                - rw Open for read/write
                - n  Don’t open the file
                - b  Return data as bytes
                - t  Decode data as string

        Returns:
            bytes/str: Large object contents
        """
        return self._with_lobject(lambda lo: lo.read(), mode=mode)

    def truncate(self, len: int = 0):
        """Truncate Large object contents.

        Args:
            len(int): truncate to this number of bytes
        """
        self._with_lobject(lambda lo: lo.truncate(len), mode="w")


class _LargeObjectMapper(generic._BaseObjectMapper[LargeObject]):
    """Maps out a resultset from a database query to a large object"""

    attributes = [
        "oid",
        "owner",
    ]


class LargeObjectCollection(generic._BaseCollection[LargeObject]):
    """An iterable collection of largeobjects indexed by name."""

    def __init__(self, cluster):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and retrieves objects from the cluster"""

        super().refresh()
        sql = util.get_sql("get_large_object")
        result = self.cluster.execute(sql)
        for mapper in [_LargeObjectMapper(x) for x in result]:
            self[mapper["oid"]] = mapper.map(
                LargeObject(cluster=self.cluster, oid=mapper["oid"], parent=self)
            )
