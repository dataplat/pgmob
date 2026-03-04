from unittest.mock import call

import pytest

from pgmob import objects
from pgmob.sql import SQL, Identifier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_key(table):
    return table.name if table.schema == "public" else f"{table.schema}.{table.name}"


def _table_tuples_to_dicts(table_tuples):
    """Convert table namedtuples to provider-style dicts."""
    return [
        {
            "name": t.name,
            "owner": t.owner,
            "schema": t.schema,
            "tablespace": t.tablespace,
            "row_security": t.row_security,
            "oid": t.oid,
        }
        for t in table_tuples
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider(mocker, table_tuples):
    """Mock metadata provider that returns table_tuples data."""
    provider = mocker.Mock()
    provider.get_tables.return_value = _table_tuples_to_dicts(table_tuples)
    return provider


@pytest.fixture
def cluster_with_mock_provider(cluster, mock_provider):
    """Cluster with metadata_provider replaced by a mock."""
    cluster.metadata_provider = mock_provider
    return cluster


@pytest.fixture
def table_collection(cluster_with_mock_provider):
    """Returns an initialized TableCollection using the mock provider."""
    return objects.TableCollection(cluster=cluster_with_mock_provider)


@pytest.fixture
def table_cursor(cursor, table_tuples):
    """Cursor that returns table tuples (used by individual Table.refresh tests)."""
    cursor.fetchall.return_value = table_tuples
    return cursor


@pytest.fixture
def table(cluster, table_tuples):
    """Returns an initialized Table object."""
    data = table_tuples[0]
    return objects.Table(
        cluster=cluster,
        name=data.name,
        owner=data.owner,
        schema=data.schema,
        oid=data.oid,
    )


# ---------------------------------------------------------------------------
# TestTable
# ---------------------------------------------------------------------------


class TestTable:
    def test_init(self, table_tuples, table):
        tbl = table_tuples[0]
        assert table.name == tbl.name
        assert table.owner == tbl.owner
        assert table.schema == tbl.schema
        assert table.tablespace is None
        assert not table.row_security
        assert table.oid == tbl.oid
        assert str(table) == f"Table('{_get_key(tbl)}')"

    def test_drop(self, cursor, table, pgmob_tester):
        table.drop()
        pgmob_tester.assertSql("DROP TABLE ", cursor)
        pgmob_tester.assertSql(table.name, cursor)
        pgmob_tester.assertSql(table.schema, cursor)

    def test_drop_cascade(self, cursor, table, pgmob_tester):
        table.drop(True)
        pgmob_tester.assertSql("DROP TABLE ", cursor)
        pgmob_tester.assertSql(table.name, cursor)
        pgmob_tester.assertSql(table.schema, cursor)
        pgmob_tester.assertSql(" CASCADE", cursor)

    def test_refresh(self, table, table_cursor, table_tuples, pgmob_tester):
        tbl = table_tuples[0]
        table.schema = "foo"
        table.refresh()
        assert table.name == tbl.name
        assert table.owner == tbl.owner
        assert table.schema == tbl.schema
        assert table.tablespace == tbl.tablespace
        assert table.row_security == tbl.row_security
        assert table.oid == tbl.oid
        assert str(table) == f"Table('{_get_key(tbl)}')"
        pgmob_tester.assertSql("FROM pg_catalog.pg_tables", table_cursor)

    def test_alter(self, table, table_cursor, table_tuples):
        src = table_tuples[0]
        table_cursor.fetchall.return_value = [src]
        fqn = SQL(".").join([Identifier(src.schema), Identifier(src.name)])
        table.name = "bar"
        table.owner = "foo"
        table.schema = "zzz"
        table.alter()
        table_cursor.execute.assert_has_calls(
            [
                call(
                    SQL("ALTER TABLE {table} OWNER TO {owner}").format(
                        table=fqn,
                        owner=Identifier("foo"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER TABLE {table} SET SCHEMA {schema}").format(
                        table=fqn,
                        schema=Identifier("zzz"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER TABLE {table} RENAME TO {new}").format(table=fqn, new=Identifier("bar")),
                    None,
                ),
            ]
        )


# ---------------------------------------------------------------------------
# TestTableCollection
# ---------------------------------------------------------------------------


class TestTableCollection:
    def test_init_populates_collection(self, table_tuples, table_collection):
        """refresh() populates collection with Table objects from provider data."""
        for result in table_collection:
            assert isinstance(result, objects.Table)

    def test_init_all_tables_present(self, table_tuples, table_collection):
        """All tables from provider are present in the collection."""
        for tbl in table_tuples:
            key = _get_key(tbl)
            assert key in table_collection

    def test_collection_indexing(self, table_tuples, table_collection):
        """Collection uses schema.name for non-public schemas, name for public."""
        for tbl in table_tuples:
            key = _get_key(tbl)
            result = table_collection[key]
            assert result.name == tbl.name
            assert result.schema == tbl.schema

    def test_metadata_mapping(self, table_tuples, table_collection):
        """All metadata fields are correctly mapped to Table objects."""
        for tbl in table_tuples:
            key = _get_key(tbl)
            result = table_collection[key]
            assert result.name == tbl.name
            assert result.owner == tbl.owner
            assert result.schema == tbl.schema
            assert result.tablespace == tbl.tablespace
            assert result.row_security == tbl.row_security
            assert result.oid == tbl.oid
            assert str(result) == f"Table('{key}')"

    def test_refresh_repopulates_collection(self, table_collection, table_tuples, mock_provider):
        """refresh() clears and repopulates the collection."""
        key = _get_key(table_tuples[0])
        table_collection[key].name = "foo"
        table_collection.refresh()
        assert table_collection[key].name == table_tuples[0].name
        assert len(table_collection[key]._changes) == 0

    def test_refresh_calls_provider(self, table_collection, mock_provider):
        """refresh() calls provider.get_tables() each time."""
        call_count_before = mock_provider.get_tables.call_count
        table_collection.refresh()
        assert mock_provider.get_tables.call_count == call_count_before + 1

    def test_empty_results(self, cluster_with_mock_provider, mock_provider):
        """Empty provider results produce an empty collection."""
        mock_provider.get_tables.return_value = []
        collection = objects.TableCollection(cluster=cluster_with_mock_provider)
        assert len(collection) == 0

    def test_get_by_oid_returns_table(self, table_tuples, table_collection, mock_provider):
        """get_by_oid() returns a Table object with correct metadata."""
        tbl = table_tuples[1]
        mock_provider.get_table.return_value = {
            "name": tbl.name,
            "owner": tbl.owner,
            "schema": tbl.schema,
            "tablespace": tbl.tablespace,
            "row_security": tbl.row_security,
            "oid": tbl.oid,
        }
        result = table_collection.get_by_oid(tbl.oid)
        assert result is not None
        assert isinstance(result, objects.Table)
        assert result.name == tbl.name
        assert result.owner == tbl.owner
        assert result.schema == tbl.schema
        assert result.tablespace == tbl.tablespace
        assert result.row_security == tbl.row_security
        assert result.oid == tbl.oid
        mock_provider.get_table.assert_called_once_with(tbl.oid)

    def test_get_by_oid_not_found(self, table_collection, mock_provider):
        """get_by_oid() returns None when provider returns None."""
        mock_provider.get_table.return_value = None
        result = table_collection.get_by_oid(99999)
        assert result is None

    def test_provider_attribute_set(self, cluster_with_mock_provider, mock_provider):
        """TableCollection stores the provider from cluster.metadata_provider."""
        collection = objects.TableCollection(cluster=cluster_with_mock_provider)
        assert collection.provider is mock_provider
