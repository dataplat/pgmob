"""Replication slots. Represent replication slots of the Postgres cluster."""
from typing import TYPE_CHECKING, Optional, Union
from ..adapters import AdapterError
from ..sql import SQL, Literal, Composable
from ..errors import PostgresError
from .. import util
from . import generic

if TYPE_CHECKING:
    from ..cluster import Cluster


class ReplicationSlot(generic._DynamicObject, generic._CollectionChild):
    """
    Postgres ReplicationSlot object. Represents a replication slot on a Postgres server.

    Args:
        name (str): name of the replication slot
        cluster (str): Postgres cluster object
        plugin (str): Replication slot plugin name
        parent (ReplicationSlotCollection): parent collection

    Attributes:
        name (str): Replication slot name
        cluster (str): Postgres cluster object
        plugin (str): Replication slot plugin name
        slot_type (str): Replication slot type
        database (str): Database name in which the slot is created
        temporary (bool): Whether the slot is temporary
        is_active (bool): Whether the slot is active
        active_pid (int): Active PID connected to the slot
        xmin (str): Slot xmin
        catalog_xmin (str): Slot catalog_xmin
        restart_lsn (str): Slot restart_lsn
        confirmed_flush_lsn (str): Slot confirmed_flush_lsn
    """

    def __init__(
        self,
        name: str,
        plugin: str,
        cluster: "Cluster" = None,
        parent: "ReplicationSlotCollection" = None,
    ):
        """Initialize a new ReplicationSlot object"""
        super().__init__(cluster=cluster, name=name, kind="REPLICATION SLOT")
        generic._CollectionChild.__init__(self, parent=parent)
        self._plugin = plugin
        self._slot_type = "logical"
        self._database = None
        self._temporary = False
        self._is_active = None
        self._active_pid = None
        self._xmin = None
        self._catalog_xmin = None
        self._restart_lsn = None
        self._confirmed_flush_lsn = None

    # properties
    @property
    def plugin(self) -> Optional[str]:
        return self._plugin

    @property
    def slot_type(self) -> str:
        return self._slot_type

    @property
    def database(self) -> Optional[str]:
        return self._database

    @property
    def temporary(self) -> bool:
        return self._temporary

    @property
    def is_active(self) -> Optional[bool]:
        return self._is_active

    @property
    def active_pid(self) -> Optional[int]:
        return self._active_pid

    @property
    def xmin(self) -> Optional[int]:
        return self._xmin

    @property
    def catalog_xmin(self) -> Optional[int]:
        return self._catalog_xmin

    @property
    def restart_lsn(self) -> Optional[int]:
        return self._restart_lsn

    @property
    def confirmed_flush_lsn(self) -> Optional[int]:
        return self._confirmed_flush_lsn

    # methods
    def drop(self, retries: int = 10) -> None:
        """Drops the replication slot from the Postres cluster

        Args:
            retries (int): number of retries after a failure. Useful when a subscriber is programmed to reconnect.
        """
        attempts = 0
        while True:
            self.refresh()
            if self.active_pid:
                self.disconnect()
            try:
                self.cluster.execute(SQL("SELECT pg_drop_replication_slot(%s)"), self.name)
                break
            except AdapterError:
                if attempts >= retries:
                    raise
                attempts += 1

    def create(self) -> None:
        """Creates a replication slot in the currently connected database based on currently configured attributes."""
        self.cluster.execute(self.script(as_composable=True))
        self.refresh()

    def script(self, as_composable: bool = False) -> Union[str, Composable]:
        """Generate a database creation script.

        Args:
            as_composable (bool): return Composable object instead of plain text

        Returns:
            Union[str, Composable]: replication slot creation script
        """
        sql = SQL("SELECT pg_create_logical_replication_slot({}, {})")

        command = sql.format(Literal(self.name), Literal(self.plugin))
        if as_composable:
            return command
        else:
            with self.cluster.adapter.cursor() as cur:
                return cur.mogrify(command)

    def disconnect(self):
        """Terminates the active pid of the replication slot"""
        self.cluster.execute(
            SQL(
                "SELECT pg_terminate_backend(active_pid) FROM pg_catalog.pg_replication_slots WHERE slot_name = %s"
            ),
            self.name,
        )

    def refresh(self):
        """Re-initializes the object, refreshing its properties"""
        super().refresh()
        sql = util.get_sql("get_replication_slot") + SQL(" WHERE slot_name = %s")
        result = self.cluster.execute(sql, self._name)
        if not result:
            raise PostgresError("Replication slot not found")
        mapper = _ReplicationSlotMapper(result[0])
        mapper.map(self)


class _ReplicationSlotMapper(generic._BaseObjectMapper[ReplicationSlot]):
    """Maps out a resultset from a replication slot query to a replication slot object"""

    attributes = [
        "name",
        "plugin",
        "slot_type",
        "database",
        "temporary",
        "is_active",
        "active_pid",
        "xmin",
        "catalog_xmin",
        "restart_lsn",
        "confirmed_flush_lsn",
    ]


class ReplicationSlotCollection(generic._BaseCollection[ReplicationSlot]):
    """An iterable collection of replication slots indexed by slot name."""

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and retrieves objects from the cluster"""

        super().refresh()
        sql = util.get_sql("get_replication_slot") + SQL(" ORDER BY slot_name")
        result = self.cluster.execute(sql)
        for mapper in [_ReplicationSlotMapper(x) for x in result]:
            self[mapper["name"]] = mapper.map(
                ReplicationSlot(
                    cluster=self.cluster,
                    name=mapper["name"],
                    plugin=mapper["plugin"],
                    parent=self,
                )
            )

    def new(
        self,
        name: str,
        plugin: str,
    ) -> ReplicationSlot:
        """Create a replication on on the current Postgres cluster. The object
        is created ephemeral and either needs to be added to the slot collection,
        or .create() needs to be executed.

        Args:
            name (str): name of the replication slot
            cluster (str): Postgres cluster object
            plugin (str): Replication slot plugin name
            temporary (bool): Whether the slot is temporary
        """
        return ReplicationSlot(
            cluster=self.cluster,
            name=name,
            plugin=plugin,
            parent=self,
        )

    def add(self, slot: ReplicationSlot):
        """Adds the replication slot object to the collection, simultaneously creating it on the cluster

        Args:
            slot (ReplicationSlot): initialized replication slot object
        """
        slot.cluster = self.cluster
        slot._parent = self
        slot.create()
        self[slot.name] = slot
