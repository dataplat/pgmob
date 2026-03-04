"""SQL-based metadata provider using pg_catalog queries.

Implements :class:`~pgmob.providers.base.MetadataProvider` using PostgreSQL
system catalog queries with version-aware SQL selection and compiled query caching.

Basic usage
-----------

:class:`SQLMetadataProvider` is created automatically by
:class:`~pgmob.cluster.Cluster` — you do not normally need to instantiate it
directly::

    from pgmob import Cluster

    cluster = Cluster(host="localhost", user="postgres", password="secret")

    # The provider is available as an attribute
    provider = cluster.metadata_provider

    # Retrieve all tables
    tables = provider.get_tables()
    for t in tables:
        print(f"{t['schema']}.{t['name']} (oid={t['oid']})")

    # Filter by schema
    public_tables = provider.get_tables(schema="public")

    # Retrieve a single table by OID
    table = provider.get_table(16384)
    if table:
        print(f"Found: {table['name']}")

    # Retrieve all roles
    for role in provider.get_roles():
        print(f"Role: {role['name']}, superuser={role['superuser']}")

    # Retrieve a single role by name
    admin = provider.get_role("postgres")

Direct provider usage (advanced)
---------------------------------

You can also use the provider independently of the collection layer::

    from pgmob import Cluster
    from pgmob.providers.sql import SQLMetadataProvider

    cluster = Cluster(host="localhost", user="postgres", password="secret")

    # Use the default provider
    provider = cluster.metadata_provider

    # Or create a provider for a specific version (useful in tests)
    from pgmob import util
    provider = SQLMetadataProvider(cluster=cluster, version=util.Version("14.5"))

    schemas = provider.get_schemas()
    sequences = provider.get_sequences(schema="public")
    views = provider.get_views(schema="public")
    procs = provider.get_procedures(schema="public")

Performance notes
-----------------

- **Query cache**: Compiled :class:`~pgmob.sql.SQL` objects are cached in
  ``_query_cache`` keyed by ``{query_name}_{major}_{minor}``.  The cache is
  populated on first use and reused for the lifetime of the provider instance,
  avoiding repeated file I/O and SQL compilation.

- **No metadata caching**: The provider does *not* cache metadata rows.
  Every call to ``get_tables()`` etc. executes a database query.  For
  read-heavy workloads, wrap this provider in a caching layer — see the
  ``CachedMetadataProvider`` example in
  :mod:`pgmob.providers.base`.

- **Version-specific SQL**: :meth:`_get_version_specific_query` selects the
  most efficient SQL file for the connected PostgreSQL version.  For
  procedures, ``get_procedure_11.sql`` is used on PG < 12 and
  ``get_procedure.sql`` on PG >= 12.

- **Parameterised queries**: All user-supplied filter values (schema names,
  role names, OIDs) are passed as query parameters — never concatenated into
  SQL strings — preventing SQL injection.
"""

import logging
from typing import TYPE_CHECKING, Any

from .. import util
from ..providers.base import MetadataProvider
from ..sql import SQL, Composable

if TYPE_CHECKING:
    from pgmob.cluster import Cluster

logger = logging.getLogger(__name__)


class SQLMetadataProvider(MetadataProvider):
    """SQL-based metadata provider using pg_catalog queries.

    Retrieves PostgreSQL object metadata by executing queries against the
    system catalog (pg_catalog). Supports PostgreSQL versions 10 through 16
    and caches compiled SQL queries by version for performance.

    Args:
        cluster: The :class:`~pgmob.cluster.Cluster` instance used to execute
            metadata queries.
        version: The PostgreSQL server version, used to select version-appropriate
            SQL queries.
    """

    def __init__(self, cluster: "Cluster", version: util.Version) -> None:
        super().__init__(cluster)
        self.version = version
        self._query_cache: dict[str, SQL] = {}
        logger.debug(
            "SQLMetadataProvider initialized: version=%s, cluster=%r",
            version,
            cluster,
        )

    def _execute_named(self, sql: Composable, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query using a named cursor and return rows as dicts.

        Uses :meth:`~pgmob.adapters.base.BaseAdapter.named_cursor` so that
        column names from the SQL ``AS`` aliases are available via
        :meth:`~pgmob.adapters.base.BaseRow._asdict`.

        Args:
            sql: Compiled SQL query to execute.
            params: Optional tuple of query parameters.

        Returns:
            List of dictionaries keyed by the column aliases in the SQL query.
        """
        with self.cluster.adapter.named_cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [row._asdict() for row in rows]

    # ------------------------------------------------------------------
    # Table metadata
    # ------------------------------------------------------------------

    def get_tables(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve table metadata from pg_catalog.

        Args:
            schema: Optional schema name filter. When provided, only tables
                belonging to that schema are returned. Uses a parameterized
                query to prevent SQL injection.

        Returns:
            List of dictionaries with keys: name, owner, schema, tablespace,
            row_security, oid.
        """
        logger.debug("get_tables(schema=%r)", schema)
        sql = util.get_sql("get_table")
        if schema:
            sql = sql + SQL(" WHERE n.nspname = %s")
            result = self._execute_named(sql, (schema,))
        else:
            result = self._execute_named(sql)
        logger.debug("get_tables returned %d rows", len(result))
        return result

    def get_table(self, oid: int) -> dict[str, Any] | None:
        """Retrieve a single table's metadata by OID.

        Args:
            oid: The table's object identifier.

        Returns:
            Dictionary with table metadata, or None if no table with that OID
            exists.
        """
        logger.debug("get_table(oid=%r)", oid)
        sql = util.get_sql("get_table") + SQL(" WHERE c.oid = %s")
        result = self._execute_named(sql, (oid,))
        if result:
            logger.debug("get_table found table with oid=%r", oid)
            return result[0]
        logger.debug("get_table: no table found with oid=%r", oid)
        return None

    # ------------------------------------------------------------------
    # Role metadata
    # ------------------------------------------------------------------

    def get_roles(self) -> list[dict[str, Any]]:
        """Retrieve all role metadata from pg_catalog.

        Returns:
            List of dictionaries with keys: name, superuser, inherit,
            createrole, createdb, login, replication, connection_limit,
            password, valid_until, oid.
        """
        logger.debug("get_roles()")
        sql = util.get_sql("get_role")
        result = self._execute_named(sql)
        logger.debug("get_roles returned %d rows", len(result))
        return result

    def get_role(self, name: str) -> dict[str, Any] | None:
        """Retrieve a single role's metadata by name.

        Uses a parameterized query to prevent SQL injection (Req 7.1, 7.2).

        Args:
            name: The role name to look up.

        Returns:
            Dictionary with role metadata, or None if no role with that name
            exists.
        """
        logger.debug("get_role(name=%r)", name)
        sql = util.get_sql("get_role") + SQL(" WHERE rolname = %s")
        result = self._execute_named(sql, (name,))
        if result:
            logger.debug("get_role found role %r", name)
            return result[0]
        logger.debug("get_role: no role found with name=%r", name)
        return None

    # ------------------------------------------------------------------
    # Database metadata
    # ------------------------------------------------------------------

    def get_databases(self) -> list[dict[str, Any]]:
        """Retrieve all database metadata from pg_catalog.

        Returns:
            List of dictionaries with keys: name, owner, encoding, collate,
            ctype, tablespace, connection_limit, oid.
        """
        logger.debug("get_databases()")
        sql = util.get_sql("get_database")
        result = self._execute_named(sql)
        logger.debug("get_databases returned %d rows", len(result))
        return result

    # ------------------------------------------------------------------
    # Schema metadata
    # ------------------------------------------------------------------

    def get_schemas(self) -> list[dict[str, Any]]:
        """Retrieve all schema metadata from pg_catalog.

        Returns:
            List of dictionaries with keys: name, owner, oid.
        """
        logger.debug("get_schemas()")
        sql = util.get_sql("get_schema")
        result = self._execute_named(sql)
        logger.debug("get_schemas returned %d rows", len(result))
        return result

    # ------------------------------------------------------------------
    # Sequence metadata
    # ------------------------------------------------------------------

    def get_sequences(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve sequence metadata from pg_catalog.

        Args:
            schema: Optional schema name filter. When provided, only sequences
                belonging to that schema are returned. Uses a parameterized
                query to prevent SQL injection.

        Returns:
            List of dictionaries with keys: name, owner, schema, data_type,
            start_value, min_value, max_value, increment_by, cycle,
            cache_size, last_value, oid.
        """
        logger.debug("get_sequences(schema=%r)", schema)
        sql = util.get_sql("get_sequence")
        if schema:
            sql = sql + SQL(" WHERE n.nspname = %s")
            result = self._execute_named(sql, (schema,))
        else:
            result = self._execute_named(sql)
        logger.debug("get_sequences returned %d rows", len(result))
        return result

    def get_sequence(self, oid: int) -> dict[str, Any] | None:
        """Retrieve a single sequence's metadata by OID.

        Args:
            oid: The sequence's object identifier.

        Returns:
            Dictionary with sequence metadata, or None if no sequence with
            that OID exists.
        """
        logger.debug("get_sequence(oid=%r)", oid)
        sql = util.get_sql("get_sequence") + SQL(" WHERE c.oid = %s")
        result = self._execute_named(sql, (oid,))
        if result:
            logger.debug("get_sequence found sequence with oid=%r", oid)
            return result[0]
        logger.debug("get_sequence: no sequence found with oid=%r", oid)
        return None

    # ------------------------------------------------------------------
    # View metadata
    # ------------------------------------------------------------------

    def get_views(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve view metadata from pg_catalog.

        Args:
            schema: Optional schema name filter. When provided, only views
                belonging to that schema are returned. Uses a parameterized
                query to prevent SQL injection.

        Returns:
            List of dictionaries with keys: name, owner, schema, oid.
        """
        logger.debug("get_views(schema=%r)", schema)
        sql = util.get_sql("get_view")
        if schema:
            sql = sql + SQL(" WHERE n.nspname = %s")
            result = self._execute_named(sql, (schema,))
        else:
            result = self._execute_named(sql)
        logger.debug("get_views returned %d rows", len(result))
        return result

    # ------------------------------------------------------------------
    # Version-specific query handling
    # ------------------------------------------------------------------

    def _get_version_specific_query(self, base_query: str) -> SQL:
        """Return a version-appropriate SQL query, loading and caching on first use.

        The cache key is ``{base_query}_{major}_{minor}`` so that different
        PostgreSQL versions are cached independently.

        For ``get_procedure``, the method selects between:
        - ``get_procedure_11.sql`` for PostgreSQL < 12
        - ``get_procedure.sql`` for PostgreSQL >= 12

        For all other base queries the base file is loaded directly.

        Args:
            base_query: Base SQL file name without extension (e.g. ``"get_procedure"``).

        Returns:
            Compiled :class:`~pgmob.sql.SQL` object appropriate for the current version.
        """
        cache_key = f"{base_query}_{self.version.major}_{self.version.minor}"
        if cache_key in self._query_cache:
            logger.debug("_get_version_specific_query: cache hit for key=%r", cache_key)
            return self._query_cache[cache_key]

        # Version-specific file selection for procedures
        if base_query == "get_procedure":
            query_name = "get_procedure_11" if self.version >= util.Version("11.0") else "get_procedure"
        else:
            query_name = base_query

        logger.debug(
            "_get_version_specific_query: loading query_name=%r for version=%s (cache_key=%r)",
            query_name,
            self.version,
            cache_key,
        )
        query = util.get_sql(query_name)
        self._query_cache[cache_key] = query
        return query

    # ------------------------------------------------------------------
    # Procedure / function metadata
    # ------------------------------------------------------------------

    def get_procedures(self, schema: str | None = None) -> list[dict[str, Any]]:
        """Retrieve procedure/function metadata from pg_catalog.

        Uses ``get_procedure_11.sql`` for PostgreSQL versions < 12 and
        ``get_procedure.sql`` for versions >= 12.  Both SQL files already
        contain a ``WHERE s.nspname <> 'pg_catalog'`` clause, so an optional
        schema filter is appended with ``AND``.

        Args:
            schema: Optional schema name filter. Uses a parameterized query
                to prevent SQL injection.

        Returns:
            List of dictionaries with keys: oid, name, schema, owner, language,
            kind, security_definer, leak_proof, strict, volatility,
            parallel_mode, argument_types.
        """
        logger.debug("get_procedures(schema=%r)", schema)
        sql = self._get_version_specific_query("get_procedure")
        if schema:
            sql = sql + SQL(" AND s.nspname = %s")
            result = self._execute_named(sql, (schema,))
        else:
            result = self._execute_named(sql)
        logger.debug("get_procedures returned %d rows", len(result))
        return result
