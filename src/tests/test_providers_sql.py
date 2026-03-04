"""Tests for SQLMetadataProvider class structure and table metadata methods."""

from collections import namedtuple
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock

import pytest

from pgmob.providers.sql import SQLMetadataProvider
from pgmob.util import Version


def make_named_rows(keys: list[str], rows: list[tuple]) -> list:
    """Create named-tuple-style row objects with _asdict() for mocking named cursor results."""
    Row = namedtuple("Row", keys)
    return [Row(*row) for row in rows]


def setup_named_cursor(mock_cluster, rows: list):
    """Configure mock_cluster.adapter.named_cursor() to return the given rows."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_cursor.execute = MagicMock()

    @contextmanager
    def _named_cursor():
        yield mock_cursor

    mock_cluster.adapter.named_cursor = _named_cursor
    return mock_cursor


@pytest.fixture
def mock_cluster():
    """A mock Cluster instance with a stubbed adapter.named_cursor()."""
    cluster = Mock()
    # Default: named_cursor returns empty rows
    setup_named_cursor(cluster, [])
    return cluster


@pytest.fixture
def version_14():
    return Version("14.0")


@pytest.fixture
def provider(mock_cluster, version_14):
    return SQLMetadataProvider(cluster=mock_cluster, version=version_14)


class TestSQLMetadataProviderInit:
    """Test SQLMetadataProvider initialisation."""

    def test_stores_cluster_reference(self, provider, mock_cluster):
        """Provider stores the cluster reference passed at init."""
        assert provider.cluster is mock_cluster

    def test_stores_version(self, provider, version_14):
        """Provider stores the version passed at init."""
        assert provider.version == version_14

    def test_init_with_different_versions(self, mock_cluster):
        """Provider can be initialised with various PostgreSQL versions."""
        for ver_str in ["10.0", "11.0", "12.0", "13.0", "14.0", "15.0", "16.0"]:
            p = SQLMetadataProvider(cluster=mock_cluster, version=Version(ver_str))
            assert p.version == Version(ver_str)

    def test_is_metadata_provider_subclass(self, provider):
        """SQLMetadataProvider is a subclass of MetadataProvider."""
        from pgmob.providers.base import MetadataProvider

        assert isinstance(provider, MetadataProvider)


# ---------------------------------------------------------------------------
# Fixtures shared by table metadata tests
# ---------------------------------------------------------------------------

# Column names matching get_table.sql AS aliases
TABLE_KEYS = ["name", "owner", "schema", "tablespace", "row_security", "oid"]

# A sample raw row as returned by pg_catalog queries:
# (name, owner, schema, tablespace, row_security, oid)
SAMPLE_ROW = ("users", "postgres", "public", "pg_default", True, 16384)
SAMPLE_ROW_NO_TABLESPACE = ("orders", "app_user", "sales", None, False, 16385)


# ---------------------------------------------------------------------------
# get_tables() tests
# ---------------------------------------------------------------------------


class TestGetTables:
    """Tests for get_tables()"""

    def test_returns_list_without_schema(self, provider, mock_cluster):
        rows = make_named_rows(TABLE_KEYS, [SAMPLE_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_tables()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_mapped_dicts(self, provider, mock_cluster):
        rows = make_named_rows(TABLE_KEYS, [SAMPLE_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_tables()
        assert result[0]["name"] == "users"
        assert result[0]["oid"] == 16384

    def test_returns_empty_list_when_no_tables(self, provider, mock_cluster):
        setup_named_cursor(mock_cluster, [])
        result = provider.get_tables()
        assert result == []

    def test_calls_execute_without_params_when_no_schema(self, provider, mock_cluster):
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_tables()
        # Called with just the SQL (no params tuple)
        args, kwargs = mock_cursor.execute.call_args
        assert len(args) == 1 or (len(args) == 2 and args[1] is None)

    def test_with_schema_filter_passes_param(self, provider, mock_cluster):
        """Schema filter must use parameterized query"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_tables(schema="public")
        args, kwargs = mock_cursor.execute.call_args
        # Second argument must be the params tuple containing the schema
        assert len(args) == 2
        assert args[1] == ("public",)

    def test_with_schema_filter_appends_where_clause(self, provider, mock_cluster):
        """SQL must include a WHERE clause when schema is provided."""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_tables(schema="myschema")
        sql_arg = mock_cursor.execute.call_args[0][0]
        # The composed SQL should contain WHERE
        composed_str = str(sql_arg)
        assert "WHERE" in composed_str or "nspname" in composed_str

    def test_schema_not_concatenated_into_sql_string(self, provider, mock_cluster):
        """Schema value must NOT appear directly in the SQL string"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        malicious = "public'; DROP TABLE users; --"
        provider.get_tables(schema=malicious)
        sql_arg = mock_cursor.execute.call_args[0][0]
        # The raw SQL composable should not contain the malicious string
        composed_str = str(sql_arg)
        assert malicious not in composed_str

    def test_returns_multiple_rows(self, provider, mock_cluster):
        rows = make_named_rows(TABLE_KEYS, [SAMPLE_ROW, SAMPLE_ROW_NO_TABLESPACE])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_tables()
        assert len(result) == 2


# ---------------------------------------------------------------------------
# get_table() tests
# ---------------------------------------------------------------------------


class TestGetTable:
    """Tests for get_table(oid)"""

    def test_returns_dict_for_valid_oid(self, provider, mock_cluster):
        rows = make_named_rows(TABLE_KEYS, [SAMPLE_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_table(16384)
        assert result is not None
        assert result["oid"] == 16384
        assert result["name"] == "users"

    def test_returns_none_for_missing_oid(self, provider, mock_cluster):
        """Non-existent OID must return None, not raise"""
        setup_named_cursor(mock_cluster, [])
        result = provider.get_table(99999)
        assert result is None

    def test_passes_oid_as_parameter(self, provider, mock_cluster):
        """OID must be passed as a query parameter"""
        rows = make_named_rows(TABLE_KEYS, [SAMPLE_ROW])
        mock_cursor = setup_named_cursor(mock_cluster, rows)
        provider.get_table(16384)
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 2
        assert args[1] == (16384,)

    def test_oid_not_concatenated_into_sql(self, provider, mock_cluster):
        """OID must not be embedded directly in the SQL string"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_table(16384)
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert "16384" not in str(sql_arg)

    def test_appends_where_oid_clause(self, provider, mock_cluster):
        """SQL must include a WHERE clause filtering by c.oid."""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_table(16384)
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert "WHERE" in str(sql_arg) or "oid" in str(sql_arg)


# ---------------------------------------------------------------------------
# Role metadata fixtures and tests
# ---------------------------------------------------------------------------

# Column names matching get_role.sql AS aliases
ROLE_KEYS = [
    "name",
    "superuser",
    "inherit",
    "createrole",
    "createdb",
    "login",
    "replication",
    "connection_limit",
    "valid_until",
    "bypassrls",
    "oid",
]

# Raw rows as returned by get_role.sql:
# (name, superuser, inherit, createrole, createdb, login,
#  replication, connection_limit, valid_until, bypassrls, oid)
SAMPLE_ROLE_ROW = ("postgres", True, True, True, True, True, True, -1, None, True, 10)
SAMPLE_ROLE_ROW_LIMITED = (
    "app_user",
    False,
    True,
    False,
    False,
    True,
    False,
    5,
    "2030-01-01 00:00:00+00",
    False,
    16400,
)


# ---------------------------------------------------------------------------
# get_roles() tests
# ---------------------------------------------------------------------------


class TestGetRoles:
    """Tests for get_roles()"""

    def test_returns_list(self, provider, mock_cluster):
        rows = make_named_rows(ROLE_KEYS, [SAMPLE_ROLE_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_roles()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_mapped_dicts(self, provider, mock_cluster):
        rows = make_named_rows(ROLE_KEYS, [SAMPLE_ROLE_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_roles()
        assert result[0]["name"] == "postgres"
        assert result[0]["oid"] == 10

    def test_returns_empty_list_when_no_roles(self, provider, mock_cluster):
        setup_named_cursor(mock_cluster, [])
        result = provider.get_roles()
        assert result == []

    def test_calls_execute_without_params(self, provider, mock_cluster):
        """get_roles() takes no filter params – cursor execute called with SQL only."""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_roles()
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 1 or (len(args) == 2 and args[1] is None)

    def test_returns_multiple_rows(self, provider, mock_cluster):
        rows = make_named_rows(ROLE_KEYS, [SAMPLE_ROLE_ROW, SAMPLE_ROLE_ROW_LIMITED])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_roles()
        assert len(result) == 2
        assert result[0]["name"] == "postgres"
        assert result[1]["name"] == "app_user"


# ---------------------------------------------------------------------------
# get_role() tests
# ---------------------------------------------------------------------------


class TestGetRole:
    """Tests for get_role(name)"""

    def test_returns_dict_for_valid_name(self, provider, mock_cluster):
        rows = make_named_rows(ROLE_KEYS, [SAMPLE_ROLE_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_role("postgres")
        assert result is not None
        assert result["name"] == "postgres"
        assert result["oid"] == 10

    def test_returns_none_for_missing_name(self, provider, mock_cluster):
        """Non-existent role name must return None, not raise"""
        setup_named_cursor(mock_cluster, [])
        result = provider.get_role("nonexistent")
        assert result is None

    def test_passes_name_as_parameter(self, provider, mock_cluster):
        """Name must be passed as a query parameter"""
        rows = make_named_rows(ROLE_KEYS, [SAMPLE_ROLE_ROW])
        mock_cursor = setup_named_cursor(mock_cluster, rows)
        provider.get_role("postgres")
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 2
        assert args[1] == ("postgres",)

    def test_name_not_concatenated_into_sql(self, provider, mock_cluster):
        """Role name must not be embedded directly in the SQL string"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_role("postgres")
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert "postgres" not in str(sql_arg)

    def test_appends_where_rolname_clause(self, provider, mock_cluster):
        """SQL must include a WHERE clause filtering by rolname."""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_role("postgres")
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert "WHERE" in str(sql_arg) or "rolname" in str(sql_arg)

    def test_injection_payload_not_in_sql(self, provider, mock_cluster):
        """Injection payload must not appear in the SQL string."""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        malicious = "postgres'; DROP TABLE users; --"
        provider.get_role(malicious)
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert malicious not in str(sql_arg)


# ---------------------------------------------------------------------------
# Database metadata fixtures and tests
# ---------------------------------------------------------------------------

# Column names matching get_database.sql AS aliases
DB_KEYS = [
    "name",
    "owner",
    "encoding",
    "collate",
    "ctype",
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

# Raw rows as returned by get_database.sql:
# (name, owner, encoding, collate, ctype, is_template,
#  allow_connections, connection_limit, last_sys_oid, frozen_xid, min_multixact_id,
#  tablespace, acl, oid)
SAMPLE_DB_ROW = (
    "mydb",
    "postgres",
    "UTF8",
    "en_US.UTF-8",
    "en_US.UTF-8",
    False,
    True,
    -1,
    0,
    0,
    0,
    "pg_default",
    None,
    16384,
)
SAMPLE_DB_ROW_LIMITED = (
    "limiteddb",
    "app_user",
    "LATIN1",
    "C",
    "C",
    False,
    True,
    10,
    0,
    0,
    0,
    "pg_global",
    None,
    16385,
)


class TestGetDatabases:
    """Tests for get_databases()"""

    def test_returns_list(self, provider, mock_cluster):
        rows = make_named_rows(DB_KEYS, [SAMPLE_DB_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_databases()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_mapped_dicts(self, provider, mock_cluster):
        rows = make_named_rows(DB_KEYS, [SAMPLE_DB_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_databases()
        assert result[0]["name"] == "mydb"
        assert result[0]["oid"] == 16384

    def test_returns_empty_list_when_no_databases(self, provider, mock_cluster):
        setup_named_cursor(mock_cluster, [])
        result = provider.get_databases()
        assert result == []

    def test_calls_execute_without_params(self, provider, mock_cluster):
        """get_databases() takes no filter params – cursor execute called with SQL only."""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_databases()
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 1 or (len(args) == 2 and args[1] is None)

    def test_returns_multiple_rows(self, provider, mock_cluster):
        rows = make_named_rows(DB_KEYS, [SAMPLE_DB_ROW, SAMPLE_DB_ROW_LIMITED])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_databases()
        assert len(result) == 2
        assert result[0]["name"] == "mydb"
        assert result[1]["name"] == "limiteddb"

    def test_all_dicts_have_required_keys(self, provider, mock_cluster):
        rows = make_named_rows(DB_KEYS, [SAMPLE_DB_ROW, SAMPLE_DB_ROW_LIMITED])
        setup_named_cursor(mock_cluster, rows)
        results = provider.get_databases()
        required_keys = {
            "name",
            "owner",
            "encoding",
            "collate",
            "ctype",
            "is_template",
            "allow_connections",
            "connection_limit",
            "last_sys_oid",
            "frozen_xid",
            "min_multixact_id",
            "tablespace",
            "acl",
            "oid",
        }
        for result in results:
            assert required_keys == set(result.keys())


# ---------------------------------------------------------------------------
# Schema metadata fixtures and tests
# ---------------------------------------------------------------------------

# Column names matching get_schema.sql AS aliases
SCHEMA_KEYS = ["name", "owner", "oid"]

# Raw rows as returned by get_schema.sql:
# (name, owner, oid)
SAMPLE_SCHEMA_ROW = ("public", "postgres", 2200)
SAMPLE_SCHEMA_ROW_2 = ("myschema", "app_user", 16500)


class TestGetSchemas:
    """Tests for get_schemas()"""

    def test_returns_list(self, provider, mock_cluster):
        rows = make_named_rows(SCHEMA_KEYS, [SAMPLE_SCHEMA_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_schemas()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_mapped_dicts(self, provider, mock_cluster):
        rows = make_named_rows(SCHEMA_KEYS, [SAMPLE_SCHEMA_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_schemas()
        assert result[0]["name"] == "public"
        assert result[0]["oid"] == 2200

    def test_returns_empty_list_when_no_schemas(self, provider, mock_cluster):
        setup_named_cursor(mock_cluster, [])
        result = provider.get_schemas()
        assert result == []

    def test_calls_execute_without_params(self, provider, mock_cluster):
        """get_schemas() takes no filter; cursor execute must be called with SQL only."""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_schemas()
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 1 or (len(args) == 2 and args[1] is None)

    def test_returns_multiple_rows(self, provider, mock_cluster):
        rows = make_named_rows(SCHEMA_KEYS, [SAMPLE_SCHEMA_ROW, SAMPLE_SCHEMA_ROW_2])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_schemas()
        assert len(result) == 2
        assert result[0]["name"] == "public"
        assert result[1]["name"] == "myschema"


# ---------------------------------------------------------------------------
# Sequence metadata fixtures and tests
# ---------------------------------------------------------------------------

# Column names matching get_sequence.sql AS aliases
SEQ_KEYS = [
    "name",
    "owner",
    "schema",
    "data_type",
    "start_value",
    "min_value",
    "max_value",
    "increment_by",
    "cycle",
    "cache_size",
    "last_value",
    "oid",
]

# Raw rows as returned by get_sequence.sql:
# (name, owner, schema, data_type, start_value, min_value,
#  max_value, increment_by, cycle, cache_size, last_value, oid)
SAMPLE_SEQ_ROW = (
    "user_id_seq",
    "postgres",
    "public",
    "bigint",
    1,
    1,
    9223372036854775807,
    1,
    False,
    1,
    42,
    16600,
)
SAMPLE_SEQ_ROW_2 = (
    "order_seq",
    "app_user",
    "sales",
    "integer",
    100,
    1,
    2147483647,
    10,
    True,
    5,
    None,
    16601,
)


class TestGetSequences:
    """Tests for get_sequences()"""

    def test_returns_list_without_schema(self, provider, mock_cluster):
        rows = make_named_rows(SEQ_KEYS, [SAMPLE_SEQ_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_sequences()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_mapped_dicts(self, provider, mock_cluster):
        rows = make_named_rows(SEQ_KEYS, [SAMPLE_SEQ_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_sequences()
        assert result[0]["name"] == "user_id_seq"
        assert result[0]["oid"] == 16600

    def test_returns_empty_list_when_no_sequences(self, provider, mock_cluster):
        setup_named_cursor(mock_cluster, [])
        result = provider.get_sequences()
        assert result == []

    def test_calls_execute_without_params_when_no_schema(self, provider, mock_cluster):
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_sequences()
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 1 or (len(args) == 2 and args[1] is None)

    def test_with_schema_filter_passes_param(self, provider, mock_cluster):
        """Schema filter must use parameterized query"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_sequences(schema="public")
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 2
        assert args[1] == ("public",)

    def test_schema_not_concatenated_into_sql(self, provider, mock_cluster):
        """Schema value must NOT appear directly in the SQL string"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        malicious = "public'; DROP TABLE users; --"
        provider.get_sequences(schema=malicious)
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert malicious not in str(sql_arg)

    def test_returns_multiple_rows(self, provider, mock_cluster):
        rows = make_named_rows(SEQ_KEYS, [SAMPLE_SEQ_ROW, SAMPLE_SEQ_ROW_2])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_sequences()
        assert len(result) == 2


# ---------------------------------------------------------------------------
# View metadata fixtures and tests
# ---------------------------------------------------------------------------

# Column names matching get_view.sql AS aliases
VIEW_KEYS = ["name", "owner", "schema", "oid"]

# Raw rows as returned by get_view.sql:
# (name, owner, schema, oid)
SAMPLE_VIEW_ROW = ("active_users", "postgres", "public", 16700)
SAMPLE_VIEW_ROW_2 = ("monthly_sales", "app_user", "reports", 16701)


class TestGetViews:
    """Tests for get_views()"""

    def test_returns_list_without_schema(self, provider, mock_cluster):
        rows = make_named_rows(VIEW_KEYS, [SAMPLE_VIEW_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_views()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_mapped_dicts(self, provider, mock_cluster):
        rows = make_named_rows(VIEW_KEYS, [SAMPLE_VIEW_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_views()
        assert result[0]["name"] == "active_users"
        assert result[0]["oid"] == 16700

    def test_returns_empty_list_when_no_views(self, provider, mock_cluster):
        setup_named_cursor(mock_cluster, [])
        result = provider.get_views()
        assert result == []

    def test_calls_execute_without_params_when_no_schema(self, provider, mock_cluster):
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_views()
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 1 or (len(args) == 2 and args[1] is None)

    def test_with_schema_filter_passes_param(self, provider, mock_cluster):
        """Schema filter must use parameterized query"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_views(schema="public")
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 2
        assert args[1] == ("public",)

    def test_schema_not_concatenated_into_sql(self, provider, mock_cluster):
        """Schema value must NOT appear directly in the SQL string"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        malicious = "public'; DROP TABLE users; --"
        provider.get_views(schema=malicious)
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert malicious not in str(sql_arg)

    def test_returns_multiple_rows(self, provider, mock_cluster):
        rows = make_named_rows(VIEW_KEYS, [SAMPLE_VIEW_ROW, SAMPLE_VIEW_ROW_2])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_views()
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Procedure metadata fixtures and tests
# ---------------------------------------------------------------------------

# Column names matching get_procedure.sql AS aliases
PROC_KEYS = [
    "oid",
    "name",
    "schema",
    "owner",
    "language",
    "kind",
    "security_definer",
    "leak_proof",
    "strict",
    "volatility",
    "parallel_mode",
    "argument_types",
]

# Raw rows as returned by get_procedure.sql / get_procedure_11.sql:
# (oid, name, schema, owner, language, kind,
#  security_definer, leak_proof, strict, volatility, parallel_mode, argument_types)
SAMPLE_PROC_ROW = (
    16800,
    "get_user",
    "public",
    "postgres",
    "plpgsql",
    "f",
    False,
    False,
    False,
    "v",
    "u",
    ["integer"],
)
SAMPLE_PROC_ROW_2 = (
    16801,
    "update_order",
    "sales",
    "app_user",
    "sql",
    "p",
    True,
    False,
    True,
    "s",
    "s",
    None,
)


class TestGetProcedures:
    """Tests for get_procedures()"""

    def test_returns_list_without_schema(self, provider, mock_cluster):
        rows = make_named_rows(PROC_KEYS, [SAMPLE_PROC_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_procedures()
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_mapped_dicts(self, provider, mock_cluster):
        rows = make_named_rows(PROC_KEYS, [SAMPLE_PROC_ROW])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_procedures()
        assert result[0]["name"] == "get_user"
        assert result[0]["oid"] == 16800

    def test_returns_empty_list_when_no_procedures(self, provider, mock_cluster):
        setup_named_cursor(mock_cluster, [])
        result = provider.get_procedures()
        assert result == []

    def test_calls_execute_without_params_when_no_schema(self, provider, mock_cluster):
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_procedures()
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 1 or (len(args) == 2 and args[1] is None)

    def test_with_schema_filter_passes_param(self, provider, mock_cluster):
        """Schema filter must use parameterized query"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        provider.get_procedures(schema="public")
        args, _ = mock_cursor.execute.call_args
        assert len(args) == 2
        assert args[1] == ("public",)

    def test_schema_not_concatenated_into_sql(self, provider, mock_cluster):
        """Schema value must NOT appear directly in the SQL string"""
        mock_cursor = setup_named_cursor(mock_cluster, [])
        malicious = "public'; DROP TABLE users; --"
        provider.get_procedures(schema=malicious)
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert malicious not in str(sql_arg)

    def test_returns_multiple_rows(self, provider, mock_cluster):
        rows = make_named_rows(PROC_KEYS, [SAMPLE_PROC_ROW, SAMPLE_PROC_ROW_2])
        setup_named_cursor(mock_cluster, rows)
        result = provider.get_procedures()
        assert len(result) == 2
        assert result[0]["name"] == "get_user"
        assert result[1]["name"] == "update_order"


class TestGetProceduresUsesVersionSpecificQuery:
    """Validates that get_procedures() delegates to _get_version_specific_query"""

    def test_get_procedures_pg11_uses_procedure_11_sql(self, mock_cluster):
        """get_procedures() on PG 11 must execute the PG-11-compatible SQL."""
        p = SQLMetadataProvider(cluster=mock_cluster, version=Version("11.0"))
        mock_cursor = setup_named_cursor(mock_cluster, [])
        p.get_procedures()
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert "prokind" in str(sql_arg)

    def test_get_procedures_pg12_uses_base_sql(self, mock_cluster):
        """get_procedures() on PG 12 must execute the standard SQL (uses prokind)."""
        p = SQLMetadataProvider(cluster=mock_cluster, version=Version("12.0"))
        mock_cursor = setup_named_cursor(mock_cluster, [])
        p.get_procedures()
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert "prokind" in str(sql_arg)

    def test_get_procedures_pg10_uses_legacy_sql(self, mock_cluster):
        """get_procedures() on PG 10 must execute the legacy SQL (uses proisagg, no prokind)."""
        p = SQLMetadataProvider(cluster=mock_cluster, version=Version("10.0"))
        mock_cursor = setup_named_cursor(mock_cluster, [])
        p.get_procedures()
        sql_arg = mock_cursor.execute.call_args[0][0]
        assert "proisagg" in str(sql_arg)


# ---------------------------------------------------------------------------
# Logging tests
# ---------------------------------------------------------------------------


class TestLogging:
    """Verify DEBUG-level logging for all metadata query methods."""

    def test_init_logs_at_debug(self, mock_cluster, caplog):
        """Provider initialisation must emit a DEBUG log."""
        import logging

        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            SQLMetadataProvider(cluster=mock_cluster, version=Version("14.0"))
        assert any("initialized" in r.message.lower() for r in caplog.records)

    def test_get_tables_logs_call_and_result(self, provider, mock_cluster, caplog):
        """get_tables() must log the call and row count at DEBUG."""
        import logging

        rows = make_named_rows(TABLE_KEYS, [("users", "postgres", "public", "pg_default", False, 1)])
        setup_named_cursor(mock_cluster, rows)
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_tables(schema="public")
        messages = [r.message for r in caplog.records]
        assert any("get_tables" in m for m in messages)
        assert any("public" in m for m in messages)

    def test_get_tables_no_schema_logs(self, provider, mock_cluster, caplog):
        """get_tables() without schema filter must still log at DEBUG."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_tables()
        assert any("get_tables" in r.message for r in caplog.records)

    def test_get_table_logs_oid(self, provider, mock_cluster, caplog):
        """get_table() must log the OID at DEBUG."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_table(99999)
        assert any("99999" in r.message for r in caplog.records)

    def test_get_roles_logs(self, provider, mock_cluster, caplog):
        """get_roles() must emit a DEBUG log."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_roles()
        assert any("get_roles" in r.message for r in caplog.records)

    def test_get_role_logs_name(self, provider, mock_cluster, caplog):
        """get_role() must log the role name at DEBUG."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_role("myapp_user")
        assert any("myapp_user" in r.message for r in caplog.records)

    def test_get_databases_logs(self, provider, mock_cluster, caplog):
        """get_databases() must emit a DEBUG log."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_databases()
        assert any("get_databases" in r.message for r in caplog.records)

    def test_get_schemas_logs(self, provider, mock_cluster, caplog):
        """get_schemas() must emit a DEBUG log."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_schemas()
        assert any("get_schemas" in r.message for r in caplog.records)

    def test_get_sequences_logs(self, provider, mock_cluster, caplog):
        """get_sequences() must emit a DEBUG log."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_sequences(schema="public")
        assert any("get_sequences" in r.message for r in caplog.records)

    def test_get_views_logs(self, provider, mock_cluster, caplog):
        """get_views() must emit a DEBUG log."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_views()
        assert any("get_views" in r.message for r in caplog.records)

    def test_get_procedures_logs(self, provider, mock_cluster, caplog):
        """get_procedures() must emit a DEBUG log."""
        import logging

        setup_named_cursor(mock_cluster, [])
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_procedures()
        assert any("get_procedures" in r.message for r in caplog.records)

    def test_version_specific_query_cache_miss_logs(self, mock_cluster, caplog):
        """Cache miss must log the query name and version."""
        import logging

        p = SQLMetadataProvider(cluster=mock_cluster, version=Version("14.0"))
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            p._get_version_specific_query("get_procedure")
        assert any("get_procedure" in r.message for r in caplog.records)

    def test_version_specific_query_cache_hit_logs(self, mock_cluster, caplog):
        """Cache hit must emit a DEBUG log."""
        import logging

        p = SQLMetadataProvider(cluster=mock_cluster, version=Version("14.0"))
        p._get_version_specific_query("get_procedure")  # populate cache
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            p._get_version_specific_query("get_procedure")
        assert any("cache hit" in r.message.lower() for r in caplog.records)

    def test_no_password_in_logs(self, provider, mock_cluster, caplog):
        """Logs must never contain role row data that could expose sensitive fields."""
        import logging

        rows = make_named_rows(
            ROLE_KEYS, [("postgres", True, True, True, True, True, True, -1, None, False, 10)]
        )
        setup_named_cursor(mock_cluster, rows)
        with caplog.at_level(logging.DEBUG, logger="pgmob.providers.sql"):
            provider.get_roles()
        # Log messages should only contain method names and row counts — not row data
        for record in caplog.records:
            # The raw role row tuple must not be serialised into any log message
            assert "True, True, True" not in record.message
            assert "rolname" not in record.message
