"""Abstract base class for metadata providers.

Defines the contract for all metadata retrieval operations across PostgreSQL
object types.  Concrete implementations (e.g.
:class:`~pgmob.providers.sql.SQLMetadataProvider`) must implement every
abstract method.

.. _custom-providers:

Custom Providers
----------------

You can extend :class:`MetadataProvider` to add caching, logging, or
alternative metadata sources.  The only requirement is that every abstract
method is implemented and returns data in the documented format.

**Example — provider with a simple TTL cache**::

    import time
    from pgmob.providers.base import MetadataProvider
    from pgmob.providers.sql import SQLMetadataProvider
    from pgmob import util
    from pgmob.sql import SQL

    class CachedMetadataProvider(MetadataProvider):
        \"\"\"Metadata provider that caches results for *ttl* seconds.

        This is useful when the same cluster object is used repeatedly in a
        tight loop and the database schema does not change between calls.

        Args:
            cluster: The connected :class:`~pgmob.cluster.Cluster` instance.
            ttl: Cache time-to-live in seconds (default: 300).
        \"\"\"

        def __init__(self, cluster, ttl: int = 300) -> None:
            super().__init__(cluster)
            self._ttl = ttl
            self._cache: dict = {}
            # Delegate actual SQL execution to the standard provider
            self._sql_provider = SQLMetadataProvider(cluster, cluster.version)

        def _get_cached(self, key: str, fetch):
            entry = self._cache.get(key)
            if entry is not None:
                cached_at, data = entry
                if time.monotonic() - cached_at < self._ttl:
                    return data
            data = fetch()
            self._cache[key] = (time.monotonic(), data)
            return data

        def get_tables(self, schema=None):
            return self._get_cached(
                f"tables:{schema}",
                lambda: self._sql_provider.get_tables(schema),
            )

        def get_table(self, oid):
            return self._sql_provider.get_table(oid)

        def get_roles(self):
            return self._get_cached("roles", self._sql_provider.get_roles)

        def get_role(self, name):
            return self._sql_provider.get_role(name)

        def get_databases(self):
            return self._get_cached("databases", self._sql_provider.get_databases)

        def get_schemas(self):
            return self._get_cached("schemas", self._sql_provider.get_schemas)

        def get_sequences(self, schema=None):
            return self._get_cached(
                f"sequences:{schema}",
                lambda: self._sql_provider.get_sequences(schema),
            )

        def get_sequence(self, oid):
            return self._sql_provider.get_sequence(oid)

        def get_views(self, schema=None):
            return self._get_cached(
                f"views:{schema}",
                lambda: self._sql_provider.get_views(schema),
            )

        def get_procedures(self, schema=None):
            return self._get_cached(
                f"procedures:{schema}",
                lambda: self._sql_provider.get_procedures(schema),
            )

Use the custom provider when creating a :class:`~pgmob.cluster.Cluster`::

    from pgmob import Cluster

    cluster = Cluster(host="localhost", user="postgres", password="secret")
    cached_provider = CachedMetadataProvider(cluster, ttl=600)
    cluster.metadata_provider = cached_provider

    # All subsequent collection accesses use the cached provider
    tables = cluster.tables  # first call hits the database
    cluster.refresh()
    tables = cluster.tables  # second call returns cached data (within TTL)

**Example — logging provider**::

    import logging
    from pgmob.providers.sql import SQLMetadataProvider

    logger = logging.getLogger(__name__)

    class LoggingMetadataProvider(SQLMetadataProvider):
        \"\"\"Wraps SQLMetadataProvider to log every metadata query.\"\"\"

        def get_tables(self, schema=None):
            logger.debug("get_tables(schema=%r)", schema)
            result = super().get_tables(schema)
            logger.debug("get_tables returned %d rows", len(result))
            return result

        # Override other methods similarly as needed …

Performance tuning
------------------

**Query caching**
    :class:`~pgmob.providers.sql.SQLMetadataProvider` caches compiled
    :class:`~pgmob.sql.SQL` objects keyed by
    ``{query_name}_{major}_{minor}``.  The cache is per-provider instance
    and lives for the lifetime of the :class:`~pgmob.cluster.Cluster`.
    Cache hits avoid file I/O and SQL compilation on every call.

**Memory management**
    Each provider instance holds only the compiled SQL objects in
    ``_query_cache`` — not the metadata rows themselves.  Metadata rows are
    returned as plain ``list[dict]`` and are not retained by the provider
    after the call returns.  For large clusters (thousands of objects) this
    means memory usage scales with the number of objects in the *collection*,
    not the provider.

**Version-specific optimisations**
    :meth:`~pgmob.providers.sql.SQLMetadataProvider._get_version_specific_query`
    selects the most efficient SQL file for the connected PostgreSQL version.
    For procedures, ``get_procedure_11.sql`` is used on PG < 12 and
    ``get_procedure.sql`` on PG >= 12.  Future versions may add further
    version-specific optimisations without changing the public API.

**Custom provider caching**
    The default :class:`~pgmob.providers.sql.SQLMetadataProvider` does *not*
    cache metadata rows — every call to ``get_tables()`` etc. hits the
    database.  If your workload reads the same metadata many times without
    schema changes, wrap the provider in a caching layer as shown in the
    ``CachedMetadataProvider`` example above.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pgmob.cluster import Cluster


class MetadataProvider(ABC):
    """Abstract base class defining the interface for PostgreSQL metadata retrieval.

    All concrete metadata providers must subclass this class and implement every
    abstract method.  The provider is initialised with a reference to the
    :class:`~pgmob.cluster.Cluster` instance so that implementations can execute
    queries against the connected PostgreSQL server.

    The default implementation is
    :class:`~pgmob.providers.sql.SQLMetadataProvider`, which is created
    automatically by :class:`~pgmob.cluster.Cluster` unless a custom provider
    is supplied via the ``metadata_provider`` constructor argument.

    See the module-level docstring for examples of custom providers, caching
    strategies, and migration guidance.

    Args:
        cluster: The :class:`~pgmob.cluster.Cluster` instance used to execute
            metadata queries.
    """

    def __init__(self, cluster: "Cluster") -> None:
        self.cluster = cluster

    # ------------------------------------------------------------------
    # Table metadata
    # ------------------------------------------------------------------

    @abstractmethod
    def get_tables(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve metadata for all tables visible to the current role.

        Args:
            schema: Optional schema name to restrict results to a single schema.
                When *None* all schemas are returned.

        Returns:
            A list of dictionaries, each containing at minimum the keys
            ``name``, ``owner``, ``schema``, and ``oid``.  Optional keys
            include ``tablespace`` and ``row_security``.
        """
        ...

    @abstractmethod
    def get_table(self, oid: int) -> dict[str, Any] | None:
        """Retrieve metadata for a single table identified by its OID.

        Args:
            oid: The PostgreSQL object identifier (OID) of the table.

        Returns:
            A dictionary with table metadata (same structure as
            :meth:`get_tables` entries) or *None* if no table with the given
            OID exists.
        """
        ...

    # ------------------------------------------------------------------
    # Role metadata
    # ------------------------------------------------------------------

    @abstractmethod
    def get_roles(self) -> list[dict[str, Any]]:
        """Retrieve metadata for all roles defined in the PostgreSQL cluster.

        Returns:
            A list of dictionaries, each containing at minimum the keys
            ``name`` and ``oid``.  Full implementations also include
            ``superuser``, ``inherit``, ``createrole``, ``createdb``,
            ``login``, ``replication``, ``connection_limit``, ``password``,
            and ``valid_until``.
        """
        ...

    @abstractmethod
    def get_role(self, name: str) -> dict[str, Any] | None:
        """Retrieve metadata for a single role identified by name.

        Args:
            name: The name of the PostgreSQL role.

        Returns:
            A dictionary with role metadata (same structure as
            :meth:`get_roles` entries) or *None* if no role with the given
            name exists.
        """
        ...

    # ------------------------------------------------------------------
    # Database metadata
    # ------------------------------------------------------------------

    @abstractmethod
    def get_databases(self) -> list[dict[str, Any]]:
        """Retrieve metadata for all databases in the PostgreSQL cluster.

        Returns:
            A list of dictionaries, each containing at minimum the keys
            ``name``, ``owner``, and ``oid``.  Full implementations also
            include ``encoding``, ``collate``, ``ctype``, ``tablespace``,
            and ``connection_limit``.
        """
        ...

    # ------------------------------------------------------------------
    # Schema metadata
    # ------------------------------------------------------------------

    @abstractmethod
    def get_schemas(self) -> list[dict[str, Any]]:
        """Retrieve metadata for all schemas in the current database.

        Returns:
            A list of dictionaries, each containing at minimum the keys
            ``name``, ``owner``, and ``oid``.
        """
        ...

    # ------------------------------------------------------------------
    # Sequence metadata
    # ------------------------------------------------------------------

    @abstractmethod
    def get_sequences(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve metadata for all sequences visible to the current role.

        Args:
            schema: Optional schema name to restrict results to a single schema.
                When *None* all schemas are returned.

        Returns:
            A list of dictionaries, each containing at minimum the keys
            ``name``, ``schema``, and ``oid``.
        """
        ...

    @abstractmethod
    def get_sequence(self, oid: int) -> dict[str, Any] | None:
        """Retrieve metadata for a single sequence identified by its OID.

        Args:
            oid: The PostgreSQL object identifier (OID) of the sequence.

        Returns:
            A dictionary with sequence metadata (same structure as
            :meth:`get_sequences` entries) or *None* if no sequence with the
            given OID exists.
        """
        ...

    # ------------------------------------------------------------------
    # View metadata
    # ------------------------------------------------------------------

    @abstractmethod
    def get_views(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve metadata for all views visible to the current role.

        Args:
            schema: Optional schema name to restrict results to a single schema.
                When *None* all schemas are returned.

        Returns:
            A list of dictionaries, each containing at minimum the keys
            ``name``, ``schema``, and ``oid``.
        """
        ...

    # ------------------------------------------------------------------
    # Procedure / function metadata
    # ------------------------------------------------------------------

    @abstractmethod
    def get_procedures(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve metadata for all procedures and functions visible to the current role.

        Args:
            schema: Optional schema name to restrict results to a single schema.
                When *None* all schemas are returned.

        Returns:
            A list of dictionaries, each containing at minimum the keys
            ``name``, ``schema``, and ``oid``.
        """
        ...
