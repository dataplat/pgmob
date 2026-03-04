"""Functional tests for SQLMetadataProvider.

Covers provider initialisation, metadata retrieval for all collection types,
metadata consistency against pg_catalog, SQL injection prevention, and role
permission enforcement.

These tests require a running PostgreSQL instance (via Docker, as configured
in conftest.py).  They are automatically skipped when Docker is unavailable.

"""

from __future__ import annotations

import pytest

from pgmob import objects
from pgmob.providers.sql import SQLMetadataProvider
from pgmob.util import Version

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provider(cluster):
    """Return the SQLMetadataProvider attached to the default cluster."""
    return cluster.metadata_provider


@pytest.fixture(scope="module")
def provider_db(cluster_db):
    """Return the SQLMetadataProvider attached to the pgmobtest database cluster."""
    return cluster_db.metadata_provider


@pytest.fixture(scope="module")
def pg_version(connect):
    """Return the PostgreSQL server version as a Version object."""
    return connect().version


@pytest.fixture(scope="module")
def db(psql, container):
    """Module-scoped database."""
    name = "pgmobtest"
    psql(f"CREATE DATABASE {name} TEMPLATE template0")
    yield name
    psql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{name}'")
    container.exec_run(f"dropdb -U postgres --if-exists {name}")


@pytest.fixture(scope="module")
def schema(psql, db):
    """Module-scoped schema inside the test database."""
    name = "tmp"
    psql(f"CREATE SCHEMA {name}", db=db)
    return name


@pytest.fixture(scope="module")
def cluster_db(connect, db):
    """Module-scoped Cluster connected to the test database."""
    return connect(db=db)


@pytest.fixture(scope="module")
def tables_setup(psql, db, cluster_db, schema):
    psql("CREATE TABLE public.test_table (a int)", db=db)
    psql(f"CREATE TABLE {schema}.test_table (a int)", db=db)
    yield cluster_db, schema


@pytest.fixture(scope="module")
def views_setup(psql, db, cluster_db, schema):
    psql("CREATE TABLE public.view_base (a int)", db=db)
    psql("CREATE VIEW public.test_view AS SELECT * FROM public.view_base", db=db)
    psql(f"CREATE TABLE {schema}.view_base (a int)", db=db)
    psql(f"CREATE VIEW {schema}.test_view AS SELECT * FROM {schema}.view_base", db=db)
    yield cluster_db, schema


@pytest.fixture(scope="module")
def sequences_setup(psql, db, cluster_db, schema):
    psql("CREATE SEQUENCE public.test_seq", db=db)
    psql(f"CREATE SEQUENCE {schema}.test_seq", db=db)
    yield cluster_db, schema


@pytest.fixture(scope="module")
def procedures_setup(psql, db, cluster_db, schema):
    result = psql("CREATE FUNCTION public.test_func() RETURNS int AS 'SELECT 1' LANGUAGE SQL", db=db)
    assert result.exit_code == 0, f"Failed to create public.test_func: {result.output}"
    result = psql(f"CREATE FUNCTION {schema}.test_func() RETURNS int AS 'SELECT 1' LANGUAGE SQL", db=db)
    assert result.exit_code == 0, f"Failed to create {schema}.test_func: {result.output}"
    yield cluster_db, schema


@pytest.fixture
def roles_setup(psql, container, cluster):
    """Create a test role for consistency and refresh tests."""
    role_name = "test_role_cons"
    psql(f"CREATE ROLE {role_name} LOGIN")
    yield cluster, role_name
    container.exec_run(f"dropuser -U postgres --if-exists {role_name}")


@pytest.fixture
def databases_setup(psql, container, cluster):
    """Create a test database for consistency tests."""
    db_name = "test_db_cons"
    psql(f"CREATE DATABASE {db_name} TEMPLATE template0")
    yield cluster, db_name
    psql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}'")
    container.exec_run(f"dropdb -U postgres --if-exists {db_name}")


@pytest.fixture(scope="module")
def schemas_setup(psql, db, cluster_db):
    """Create an extra schema for consistency and refresh tests."""
    extra_schema = "test_extra_schema"
    psql(f"CREATE SCHEMA {extra_schema}", db=db)
    yield cluster_db, extra_schema


@pytest.fixture
def limited_role(psql, container, hostname, pg_password, db):
    """Create a low-privilege role with SELECT on public schema only."""
    role_name = "sec_limited_role"
    psql(f"CREATE ROLE {role_name} LOGIN PASSWORD 'LimitedPass1!'")
    psql(f"GRANT CONNECT ON DATABASE {db} TO {role_name}")
    psql(f"GRANT USAGE ON SCHEMA public TO {role_name}", db=db)
    psql(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role_name}", db=db)

    def _connect():
        from pgmob.adapters import psycopg2 as _psycopg2
        from pgmob.cluster import Cluster

        adapter = _psycopg2.Psycopg2Adapter(cursor_factory=None)
        return Cluster(
            host=hostname,
            port=5432,
            user=role_name,
            password="LimitedPass1!",
            dbname=db,
            adapter=adapter,
        )

    yield role_name, _connect
    container.exec_run(f"dropuser -U postgres --if-exists {role_name}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_TABLE_KEYS = {"name", "owner", "schema", "oid"}
REQUIRED_ROLE_KEYS = {
    "name",
    "superuser",
    "inherit",
    "createrole",
    "createdb",
    "login",
    "replication",
    "connection_limit",
    "oid",
}
REQUIRED_DATABASE_KEYS = {
    "name",
    "owner",
    "encoding",
    "collation",
    "character_type",
    "tablespace",
    "connection_limit",
    "oid",
}
REQUIRED_SCHEMA_KEYS = {"name", "owner", "oid"}
REQUIRED_SEQUENCE_KEYS = {"name", "owner", "schema", "oid"}
REQUIRED_VIEW_KEYS = {"name", "owner", "schema", "oid"}
REQUIRED_PROCEDURE_KEYS = {"name", "schema", "owner", "oid"}

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE pg_class; --",
    "public' OR '1'='1",
    "public'; SELECT * FROM pg_shadow; --",
    "public' UNION SELECT rolname, rolpassword FROM pg_authid --",
    "1; EXEC xp_cmdshell('whoami'); --",
    "' OR 1=1 --",
    "admin'--",
    "public' AND 1=CAST((SELECT version()) AS INT)--",
]


def _assert_metadata_keys(items: list[dict], required_keys: set, label: str) -> None:
    assert len(items) > 0, f"Expected at least one {label} but got none"
    for item in items:
        missing = required_keys - item.keys()
        assert not missing, f"{label} metadata missing keys: {missing}. Got: {set(item.keys())}"


# ---------------------------------------------------------------------------
# Provider initialisation
# ---------------------------------------------------------------------------


class TestProviderInitialisation:
    def test_provider_wiring(self, cluster):
        """Provider is a SQLMetadataProvider with correct version and cluster reference."""
        provider = cluster.metadata_provider
        assert isinstance(provider, SQLMetadataProvider)
        assert provider.version == cluster.version
        assert provider.cluster is cluster

    def test_version_properties(self, pg_version):
        """Version is >= 10 with integer major and minor components."""
        assert pg_version >= Version("10.0"), f"Unexpected version: {pg_version}"
        assert isinstance(pg_version.major, int)
        assert isinstance(pg_version.minor, int)

    def test_provider_integrity(self, cluster):
        """Provider exposes version and cluster attributes; query cache is a dict."""
        provider = cluster.metadata_provider
        assert hasattr(provider, "version") and provider.version is not None
        assert provider.cluster is cluster
        assert isinstance(provider._query_cache, dict)

    def test_repeated_invalid_lookups_are_safe(self, provider, tables_setup):
        """Repeated invalid OID and role lookups all return None without side effects."""
        cluster_db, _ = tables_setup
        for _ in range(5):
            assert cluster_db.metadata_provider.get_table(999_999_999) is None
            assert provider.get_role("__ghost_role__") is None

    def test_nonexistent_schema_does_not_corrupt_cache(self, tables_setup):
        """Querying a non-existent schema does not corrupt the query cache."""
        cluster_db, _ = tables_setup
        provider = cluster_db.metadata_provider
        cache_before = dict(provider._query_cache)
        provider.get_tables(schema="__no_such_schema__")
        for key, value in cache_before.items():
            assert provider._query_cache[key] is value


# ---------------------------------------------------------------------------
# Table metadata
# ---------------------------------------------------------------------------


class TestTableMetadata:
    def test_get_tables_structure_and_filter(self, tables_setup):
        """get_tables() returns dicts with required keys; schema filter and OID lookup work."""
        cluster_db, schema = tables_setup
        provider = cluster_db.metadata_provider

        all_tables = provider.get_tables()
        assert isinstance(all_tables, list)
        _assert_metadata_keys(all_tables, REQUIRED_TABLE_KEYS, "table")
        assert all(isinstance(t["oid"], int) and t["oid"] > 0 for t in all_tables)

        assert all(r["schema"] == schema for r in provider.get_tables(schema=schema))
        assert provider.get_tables(schema="__nonexistent_schema__") == []

        target = next((t for t in provider.get_tables(schema="public") if t["name"] == "test_table"), None)
        assert target is not None
        fetched = provider.get_table(target["oid"])
        assert fetched is not None and fetched["name"] == "test_table" and fetched["oid"] == target["oid"]
        assert provider.get_table(999999999) is None

    def test_invalid_oid_and_zero_oid_return_none(self, tables_setup):
        """get_table() with non-existent, zero, or max OIDs returns None."""
        cluster_db, _ = tables_setup
        provider = cluster_db.metadata_provider
        assert provider.get_table(0) is None
        assert provider.get_table(999_999_999) is None
        assert provider.get_table(2_147_483_647) is None

    def test_nonexistent_schema_returns_list(self, tables_setup):
        """Non-existent schema always returns a list, never None; special chars are safe."""
        cluster_db, _ = tables_setup
        provider = cluster_db.metadata_provider
        assert isinstance(provider.get_tables(schema="__no_such_schema__"), list)
        assert provider.get_tables(schema="schema-with-dashes") == []
        assert isinstance(provider.get_tables(schema=""), list)


# ---------------------------------------------------------------------------
# Role metadata
# ---------------------------------------------------------------------------


class TestRoleMetadata:
    def test_get_roles_structure_and_lookup(self, provider):
        """get_roles() returns dicts with required keys; get_role() lookup works."""
        result = provider.get_roles()
        assert isinstance(result, list) and len(result) > 0
        _assert_metadata_keys(result, REQUIRED_ROLE_KEYS, "role")

        postgres = provider.get_role("postgres")
        assert postgres is not None and postgres["name"] == "postgres" and postgres["superuser"] is True
        assert provider.get_role("__nonexistent_role__") is None
        assert provider.get_role("") is None
        assert provider.get_role("'; DROP TABLE pg_roles; --") is None


# ---------------------------------------------------------------------------
# Database metadata
# ---------------------------------------------------------------------------


class TestDatabaseMetadata:
    def test_get_databases_structure(self, provider, db):
        """get_databases() returns dicts with required keys and includes known databases."""
        result = provider.get_databases()
        assert isinstance(result, list) and len(result) > 0
        _assert_metadata_keys(result, REQUIRED_DATABASE_KEYS, "database")
        assert "postgres" in [d["name"] for d in result]


# ---------------------------------------------------------------------------
# Schema metadata
# ---------------------------------------------------------------------------


class TestSchemaMetadata:
    def test_get_schemas_structure(self, provider_db, schema):
        """get_schemas() returns dicts with required keys and includes known schemas."""
        result = provider_db.get_schemas()
        assert isinstance(result, list) and len(result) > 0
        _assert_metadata_keys(result, REQUIRED_SCHEMA_KEYS, "schema")
        names = [s["name"] for s in result]
        assert "public" in names and schema in names


# ---------------------------------------------------------------------------
# Sequence metadata
# ---------------------------------------------------------------------------


class TestSequenceMetadata:
    def test_get_sequences_structure_and_filter(self, sequences_setup):
        """get_sequences() returns dicts with required keys; schema filter works."""
        cluster_db, schema = sequences_setup
        provider = cluster_db.metadata_provider

        result = provider.get_sequences()
        assert isinstance(result, list)
        _assert_metadata_keys(result, REQUIRED_SEQUENCE_KEYS, "sequence")
        assert all(r["schema"] == schema for r in provider.get_sequences(schema=schema))
        assert provider.get_sequences(schema="__nonexistent__") == []


# ---------------------------------------------------------------------------
# View metadata
# ---------------------------------------------------------------------------


class TestViewMetadata:
    def test_get_views_structure_and_filter(self, views_setup):
        """get_views() returns dicts with required keys; schema filter works."""
        cluster_db, schema = views_setup
        provider = cluster_db.metadata_provider

        result = provider.get_views()
        assert isinstance(result, list)
        _assert_metadata_keys(result, REQUIRED_VIEW_KEYS, "view")
        assert all(r["schema"] == schema for r in provider.get_views(schema=schema))
        assert provider.get_views(schema="__nonexistent__") == []


# ---------------------------------------------------------------------------
# Procedure metadata
# ---------------------------------------------------------------------------


class TestProcedureMetadata:
    def test_get_procedures_structure_and_filter(self, procedures_setup):
        """get_procedures() returns dicts with required keys; schema filter works."""
        cluster_db, schema = procedures_setup
        provider = cluster_db.metadata_provider

        result = provider.get_procedures()
        assert isinstance(result, list)
        _assert_metadata_keys(result, REQUIRED_PROCEDURE_KEYS, "procedure")
        assert all(r["schema"] == schema for r in provider.get_procedures(schema=schema))
        assert provider.get_procedures(schema="__nonexistent__") == []

    def test_version_specific_query_and_caching(self, procedures_setup):
        """Version-specific SQL is selected and cached; cache hit returns same object."""
        cluster_db, _ = procedures_setup
        provider = SQLMetadataProvider(cluster=cluster_db, version=cluster_db.version)
        provider.get_procedures()

        version = cluster_db.version
        assert f"get_procedure_{version.major}_{version.minor}" in provider._query_cache
        assert provider._get_version_specific_query("get_procedure") is provider._get_version_specific_query(
            "get_procedure"
        )

    def test_pg11_procedure_kinds(self, procedures_setup):
        """On PG >= 11, function kind 'f' is present; PG 10 has no 'p' kind."""
        cluster_db, _ = procedures_setup
        version = cluster_db.version
        result = cluster_db.metadata_provider.get_procedures(schema="public")
        if version.major >= 11:
            assert "f" in {r.get("kind") for r in result}
        else:
            assert all(r.get("kind") != "p" for r in result)


# ---------------------------------------------------------------------------
# Metadata consistency
# ---------------------------------------------------------------------------


class TestMetadataConsistency:
    def test_table_metadata_matches_pg_catalog(self, tables_setup):
        """Table metadata from provider matches pg_catalog directly."""
        cluster_db, _ = tables_setup
        provider = cluster_db.metadata_provider
        target = next((t for t in provider.get_tables(schema="public") if t["name"] == "test_table"), None)
        assert target is not None

        rows = cluster_db.execute(
            "SELECT c.relname, r.rolname, n.nspname, c.oid "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid "
            "JOIN pg_catalog.pg_roles r ON c.relowner = r.oid "
            "WHERE c.relname = 'test_table' AND n.nspname = 'public' AND c.relkind = 'r'"
        )
        assert len(rows) == 1
        assert target["name"] == rows[0][0]
        assert target["owner"] == rows[0][1]
        assert target["schema"] == rows[0][2]
        assert target["oid"] == rows[0][3]

    def test_refresh_reflects_new_table(self, tables_setup, psql, db):
        """After creating a new table, refresh() includes it; multiple refreshes are idempotent."""
        cluster_db, _ = tables_setup
        collection = objects.TableCollection(cluster=cluster_db)
        assert "new_table" not in collection

        psql("CREATE TABLE public.new_table (a int)", db=db)
        collection.refresh()
        assert "new_table" in collection

        names_after = {t.name for t in collection}
        collection.refresh()
        assert {t.name for t in collection} == names_after


# ---------------------------------------------------------------------------
# SQL injection prevention
# ---------------------------------------------------------------------------


class TestSQLInjectionPrevention:
    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_get_tables_injection_payload_returns_empty(self, tables_setup, payload):
        cluster_db, _ = tables_setup
        result = cluster_db.metadata_provider.get_tables(schema=payload)
        assert result == [], f"Expected empty list for payload {payload!r}, got {result!r}"

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_get_sequences_injection_payload_returns_empty(self, sequences_setup, payload):
        cluster_db, _ = sequences_setup
        result = cluster_db.metadata_provider.get_sequences(schema=payload)
        assert result == [], f"Expected empty list for payload {payload!r}, got {result!r}"

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_get_views_injection_payload_returns_empty(self, views_setup, payload):
        cluster_db, _ = views_setup
        result = cluster_db.metadata_provider.get_views(schema=payload)
        assert result == [], f"Expected empty list for payload {payload!r}, got {result!r}"

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_get_procedures_injection_payload_returns_empty(self, procedures_setup, payload):
        cluster_db, _ = procedures_setup
        result = cluster_db.metadata_provider.get_procedures(schema=payload)
        assert result == [], f"Expected empty list for payload {payload!r}, got {result!r}"

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    def test_get_role_injection_payload_returns_none(self, provider, payload):
        assert provider.get_role(payload) is None, f"Expected None for payload {payload!r}"

    def test_injection_does_not_drop_tables(self, tables_setup):
        """A DROP TABLE injection payload does not actually drop any table."""
        cluster_db, _ = tables_setup
        cluster_db.metadata_provider.get_tables(schema="public'; DROP TABLE public.test_table; --")
        names = {t["name"] for t in cluster_db.metadata_provider.get_tables(schema="public")}
        assert "test_table" in names

    def test_injection_does_not_expose_pg_shadow(self, tables_setup):
        """A UNION-based injection payload does not expose pg_shadow data."""
        cluster_db, _ = tables_setup
        result = cluster_db.metadata_provider.get_tables(
            schema="public' UNION SELECT usename, passwd FROM pg_shadow --"
        )
        assert result == []


# ---------------------------------------------------------------------------
# Role permissions
# ---------------------------------------------------------------------------


class TestRolePermissions:
    def test_limited_role_can_query_tables(self, tables_setup, limited_role):
        """A limited role can retrieve table metadata for schemas it has USAGE on."""
        cluster_db, _ = tables_setup
        _, connect_fn = limited_role
        limited_cluster = connect_fn()
        try:
            result = limited_cluster.metadata_provider.get_tables(schema="public")
            assert "test_table" in {t["name"] for t in result}
        finally:
            limited_cluster.adapter.close_connection()

    def test_limited_role_cannot_escalate_to_superuser(self, limited_role):
        """A limited role must not be a superuser after provider queries."""
        _, connect_fn = limited_role
        limited_cluster = connect_fn()
        try:
            roles = limited_cluster.metadata_provider.get_roles()
            current_user = limited_cluster.execute("SELECT current_user")[0][0]
            role_data = next((r for r in roles if r["name"] == current_user), None)
            assert role_data is not None
            assert role_data["superuser"] is False
        finally:
            limited_cluster.adapter.close_connection()

    def test_limited_role_metadata_consistent_with_superuser(self, tables_setup, limited_role):
        """OIDs and schemas match between limited-role and superuser views."""
        cluster_db, _ = tables_setup
        _, connect_fn = limited_role
        limited_cluster = connect_fn()
        try:
            su_tables = {t["name"]: t for t in cluster_db.metadata_provider.get_tables(schema="public")}
            for name, lm in {
                t["name"]: t for t in limited_cluster.metadata_provider.get_tables(schema="public")
            }.items():
                if name in su_tables:
                    assert lm["oid"] == su_tables[name]["oid"]
                    assert lm["schema"] == su_tables[name]["schema"]
        finally:
            limited_cluster.adapter.close_connection()

    def test_provider_uses_current_session_role(self, limited_role):
        """Provider executes under the current session role."""
        _, connect_fn = limited_role
        limited_cluster = connect_fn()
        try:
            assert limited_cluster.execute("SELECT current_user")[0][0] == "sec_limited_role"
            assert isinstance(limited_cluster.metadata_provider.get_roles(), list)
        finally:
            limited_cluster.adapter.close_connection()


# ---------------------------------------------------------------------------
# Per-type metadata consistency against pg_catalog
# ---------------------------------------------------------------------------


class TestRoleMetadataConsistency:
    def test_role_metadata_matches_pg_catalog(self, roles_setup):
        """Role metadata from provider matches pg_catalog.pg_roles (name, superuser, login, oid)."""
        cluster, role_name = roles_setup
        roles = cluster.metadata_provider.get_roles()
        target = next((r for r in roles if r["name"] == role_name), None)
        assert target is not None, f"Role {role_name!r} not found via provider"

        rows = cluster.execute(
            f"SELECT rolname, rolsuper, rolcanlogin, oid FROM pg_catalog.pg_roles WHERE rolname = '{role_name}'"
        )
        assert len(rows) == 1
        assert target["name"] == rows[0][0]
        assert target["superuser"] == rows[0][1]
        assert target["login"] == rows[0][2]
        assert target["oid"] == rows[0][3]


class TestDatabaseMetadataConsistency:
    def test_database_metadata_matches_pg_catalog(self, databases_setup):
        """Database metadata from provider matches pg_catalog.pg_database (name, owner, oid, count)."""
        cluster, db_name = databases_setup
        databases = cluster.metadata_provider.get_databases()
        target = next((d for d in databases if d["name"] == db_name), None)
        assert target is not None, f"Database {db_name!r} not found via provider"

        rows = cluster.execute(
            "SELECT d.datname, r.rolname, d.oid "
            "FROM pg_catalog.pg_database d "
            "JOIN pg_catalog.pg_roles r ON d.datdba = r.oid "
            f"WHERE d.datname = '{db_name}'"
        )
        assert len(rows) == 1
        assert target["name"] == rows[0][0]
        assert target["owner"] == rows[0][1]
        assert target["oid"] == rows[0][2]

        count_rows = cluster.execute("SELECT count(*) FROM pg_catalog.pg_database")
        assert len(databases) == count_rows[0][0]


class TestSequenceMetadataConsistency:
    def test_sequence_metadata_matches_pg_catalog(self, sequences_setup):
        """Sequence metadata from provider matches pg_catalog (name, schema, oid)."""
        cluster_db, schema = sequences_setup
        seqs = cluster_db.metadata_provider.get_sequences(schema="public")
        target = next((s for s in seqs if s["name"] == "test_seq"), None)
        assert target is not None, "test_seq not found via provider"

        rows = cluster_db.execute(
            "SELECT c.relname, n.nspname, c.oid "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid "
            "WHERE c.relname = 'test_seq' AND n.nspname = 'public' AND c.relkind = 'S'"
        )
        assert len(rows) == 1
        assert target["name"] == rows[0][0]
        assert target["schema"] == rows[0][1]
        assert target["oid"] == rows[0][2]


class TestSchemaMetadataConsistency:
    def test_schema_metadata_matches_pg_catalog(self, schemas_setup):
        """Schema metadata from provider matches pg_catalog.pg_namespace (name, owner, oid)."""
        cluster_db, extra_schema = schemas_setup
        schemas = cluster_db.metadata_provider.get_schemas()
        target = next((s for s in schemas if s["name"] == extra_schema), None)
        assert target is not None, f"Schema {extra_schema!r} not found via provider"

        rows = cluster_db.execute(
            "SELECT n.nspname, r.rolname, n.oid "
            "FROM pg_catalog.pg_namespace n "
            "JOIN pg_catalog.pg_roles r ON n.nspowner = r.oid "
            f"WHERE n.nspname = '{extra_schema}'"
        )
        assert len(rows) == 1
        assert target["name"] == rows[0][0]
        assert target["owner"] == rows[0][1]
        assert target["oid"] == rows[0][2]


# ---------------------------------------------------------------------------
# refresh() reflects database changes
# ---------------------------------------------------------------------------


class TestRefreshReflectsChanges:
    def test_refresh_reflects_new_table(self, tables_setup, psql, db):
        """After creating a new table, refresh() includes it in the collection."""
        cluster_db, _ = tables_setup
        collection = objects.TableCollection(cluster=cluster_db)
        assert "cons_new_table" not in collection

        psql("CREATE TABLE public.cons_new_table (x int)", db=db)
        collection.refresh()
        assert "cons_new_table" in collection

    def test_refresh_reflects_dropped_table(self, cluster_db, psql, db):
        """After dropping a table, refresh() removes it from the collection."""
        psql("CREATE TABLE public.drop_me (a int)", db=db)
        collection = objects.TableCollection(cluster=cluster_db)
        assert "drop_me" in collection

        psql("DROP TABLE public.drop_me", db=db)
        collection.refresh()
        assert "drop_me" not in collection

    def test_refresh_reflects_new_role(self, psql, container, cluster):
        """After creating a role, refresh() includes it in the RoleCollection."""
        new_role = "cons_refresh_role"
        collection = objects.RoleCollection(cluster=cluster)
        assert new_role not in collection

        psql(f"CREATE ROLE {new_role}")
        try:
            collection.refresh()
            assert new_role in collection
        finally:
            container.exec_run(f"dropuser -U postgres --if-exists {new_role}")

    def test_refresh_reflects_dropped_role(self, roles_setup, psql, container):
        """After dropping a role, refresh() removes it from the RoleCollection."""
        cluster, role_name = roles_setup
        collection = objects.RoleCollection(cluster=cluster)
        assert role_name in collection

        container.exec_run(f"dropuser -U postgres --if-exists {role_name}")
        collection.refresh()
        assert role_name not in collection

    def test_refresh_reflects_new_schema(self, schemas_setup, psql, db):
        """After creating a schema, refresh() includes it in the SchemaCollection."""
        cluster_db, _ = schemas_setup
        new_schema = "cons_brand_new_schema"
        collection = objects.SchemaCollection(cluster=cluster_db)
        assert new_schema not in collection

        psql(f"CREATE SCHEMA {new_schema}", db=db)
        collection.refresh()
        assert new_schema in collection

    def test_refresh_reflects_new_sequence(self, sequences_setup, psql, db):
        """After creating a sequence, refresh() includes it in the SequenceCollection."""
        cluster_db, _ = sequences_setup
        collection = objects.SequenceCollection(cluster=cluster_db)
        assert "cons_new_seq" not in collection

        psql("CREATE SEQUENCE public.cons_new_seq", db=db)
        collection.refresh()
        assert "cons_new_seq" in collection

    def test_provider_reflects_new_table_directly(self, tables_setup, psql, db):
        """Provider get_tables() returns a newly created table without refresh."""
        cluster_db, _ = tables_setup
        before = {t["name"] for t in cluster_db.metadata_provider.get_tables(schema="public")}
        assert "cons_direct_table" not in before

        psql("CREATE TABLE public.cons_direct_table (y int)", db=db)
        after = {t["name"] for t in cluster_db.metadata_provider.get_tables(schema="public")}
        assert "cons_direct_table" in after


# ---------------------------------------------------------------------------
# Provider does NOT cache metadata results by default
# ---------------------------------------------------------------------------


class TestNoDefaultMetadataCaching:
    def test_provider_does_not_cache_table_results(self, tables_setup, psql, db):
        """Two consecutive get_tables() calls reflect live DB state (no stale cache)."""
        cluster_db, _ = tables_setup
        first = {t["name"] for t in cluster_db.metadata_provider.get_tables(schema="public")}
        assert "cons_nocache_table" not in first

        psql("CREATE TABLE public.cons_nocache_table (z int)", db=db)
        second = {t["name"] for t in cluster_db.metadata_provider.get_tables(schema="public")}
        assert "cons_nocache_table" in second

    def test_provider_does_not_cache_role_results(self, psql, container, cluster):
        """Two consecutive get_roles() calls reflect live DB state."""
        new_role = "cons_nocache_role"
        first = {r["name"] for r in cluster.metadata_provider.get_roles()}
        assert new_role not in first

        psql(f"CREATE ROLE {new_role}")
        try:
            second = {r["name"] for r in cluster.metadata_provider.get_roles()}
            assert new_role in second
        finally:
            container.exec_run(f"dropuser -U postgres --if-exists {new_role}")


# ---------------------------------------------------------------------------
# Idempotency of multiple refresh() calls
# ---------------------------------------------------------------------------


class TestRefreshIdempotency:
    def test_table_collection_refresh_idempotent(self, tables_setup):
        """Multiple refresh() calls without DB changes produce identical table sets."""
        cluster_db, _ = tables_setup
        collection = objects.TableCollection(cluster=cluster_db)
        names_first = {t.name for t in collection}

        collection.refresh()
        names_second = {t.name for t in collection}

        collection.refresh()
        names_third = {t.name for t in collection}

        assert names_first == names_second == names_third

    def test_role_collection_refresh_idempotent(self, cluster):
        """Multiple refresh() calls without DB changes produce identical role sets."""
        collection = objects.RoleCollection(cluster=cluster)
        names_first = {r.name for r in collection}

        collection.refresh()
        names_second = {r.name for r in collection}

        collection.refresh()
        names_third = {r.name for r in collection}

        assert names_first == names_second == names_third

    def test_database_collection_refresh_idempotent(self, cluster):
        """Multiple refresh() calls without DB changes produce identical database sets."""
        collection = objects.DatabaseCollection(cluster=cluster)
        names_first = {d.name for d in collection}

        collection.refresh()
        names_second = {d.name for d in collection}

        collection.refresh()
        names_third = {d.name for d in collection}

        assert names_first == names_second == names_third

    def test_schema_collection_refresh_idempotent(self, cluster_db, schema):
        """Multiple refresh() calls without DB changes produce identical schema sets."""
        collection = objects.SchemaCollection(cluster=cluster_db)
        names_first = {s.name for s in collection}

        collection.refresh()
        names_second = {s.name for s in collection}

        collection.refresh()
        names_third = {s.name for s in collection}

        assert names_first == names_second == names_third

    def test_sequence_collection_refresh_idempotent(self, sequences_setup):
        """Multiple refresh() calls without DB changes produce identical sequence sets."""
        cluster_db, _ = sequences_setup
        collection = objects.SequenceCollection(cluster=cluster_db)
        names_first = {s.name for s in collection}

        collection.refresh()
        names_second = {s.name for s in collection}

        assert names_first == names_second

    def test_provider_get_tables_idempotent(self, tables_setup):
        """Calling get_tables() multiple times returns the same result."""
        cluster_db, _ = tables_setup
        first = cluster_db.metadata_provider.get_tables(schema="public")
        second = cluster_db.metadata_provider.get_tables(schema="public")

        assert {t["name"] for t in first} == {t["name"] for t in second}

    def test_provider_get_roles_idempotent(self, provider):
        """Calling get_roles() multiple times returns the same result."""
        first = {r["name"] for r in provider.get_roles()}
        second = {r["name"] for r in provider.get_roles()}
        assert first == second

    def test_provider_get_databases_idempotent(self, provider):
        """Calling get_databases() multiple times returns the same result."""
        first = {d["name"] for d in provider.get_databases()}
        second = {d["name"] for d in provider.get_databases()}
        assert first == second
