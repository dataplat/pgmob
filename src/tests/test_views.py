from unittest.mock import call

import pytest

from pgmob import objects
from pgmob.sql import SQL, Identifier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _view_tuples_to_dicts(view_tuples):
    """Convert view namedtuples to provider-style dicts."""
    return [
        {
            "name": v.name,
            "owner": v.owner,
            "schema": v.schema,
            "oid": v.oid,
        }
        for v in view_tuples
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider(mocker, view_tuples):
    """Mock metadata provider that returns view_tuples data."""
    provider = mocker.Mock()
    provider.get_views.return_value = _view_tuples_to_dicts(view_tuples)
    return provider


@pytest.fixture
def cluster_with_mock_provider(cluster, mock_provider):
    """Cluster with metadata_provider replaced by a mock."""
    cluster.metadata_provider = mock_provider
    return cluster


@pytest.fixture
def view_cursor(cursor, view_tuples):
    """Cursor that returns view tuples"""
    cursor.fetchall.return_value = view_tuples
    return cursor


@pytest.fixture
def view_collection(cluster_with_mock_provider):
    """Returns an initialized ViewCollection object using the mock provider."""
    collection = objects.ViewCollection(cluster=cluster_with_mock_provider)
    return collection


@pytest.fixture
def view(cluster, view_tuples):
    """Returns an initialized View object"""
    data = view_tuples[0]
    return objects.View(
        cluster=cluster,
        name=data.name,
        owner=data.owner,
        schema=data.schema,
        oid=data.oid,
    )


def _get_key(view):
    return view.name if view.schema == "public" else f"{view.schema}.{view.name}"


class TestView:
    def test_init(self, view_tuples, view):
        v = view_tuples[0]
        assert view.name == v.name
        assert view.owner == v.owner
        assert view.schema == v.schema
        assert view.oid == v.oid
        assert str(view) == f"View('{_get_key(v)}')"

    def test_drop(self, cursor, view, pgmob_tester):
        view.drop()
        pgmob_tester.assertSql("DROP VIEW ", cursor)
        pgmob_tester.assertSql(view.name, cursor)
        pgmob_tester.assertSql(view.schema, cursor)

    def test_drop_cascade(self, cursor, view, pgmob_tester):
        view.drop(True)
        pgmob_tester.assertSql("DROP VIEW ", cursor)
        pgmob_tester.assertSql(view.name, cursor)
        pgmob_tester.assertSql(view.schema, cursor)
        pgmob_tester.assertSql(" CASCADE", cursor)

    def test_refresh(self, view, view_cursor, view_tuples, pgmob_tester):
        v = view_tuples[0]
        view.schema = "foo"
        view.refresh()
        assert view.name == v.name
        assert view.owner == v.owner
        assert view.schema == v.schema
        assert view.oid == v.oid
        assert str(view) == f"View('{_get_key(v)}')"
        pgmob_tester.assertSql("FROM pg_catalog.pg_views", view_cursor)

    def test_alter(self, view, view_cursor, view_tuples):
        src = view_tuples[0]
        view_cursor.fetchall.return_value = [src]
        fqn = SQL(".").join([Identifier(view.schema), Identifier(view.name)])
        view.name = "bar"
        view.owner = "foo"
        view.schema = "zzz"
        view.alter()
        view_cursor.execute.assert_has_calls(
            [
                call(
                    SQL("ALTER VIEW {view} OWNER TO {owner}").format(
                        view=fqn,
                        owner=Identifier("foo"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER VIEW {view} SET SCHEMA {schema}").format(
                        view=fqn,
                        schema=Identifier("zzz"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER VIEW {view} RENAME TO {new}").format(view=fqn, new=Identifier("bar")),
                    None,
                ),
            ]
        )


class TestViewCollection:
    def test_init(self, view_tuples, view_collection):
        for result in view_collection:
            assert isinstance(result, objects.View)
        for v in view_tuples:
            key = _get_key(v)
            result = view_collection[key]
            assert result.name == v.name
            assert result.owner == v.owner
            assert result.schema == v.schema
            assert result.oid == v.oid
            assert str(result) == f"View('{key}')"

    def test_refresh(self, view_collection: objects.ViewCollection, view_tuples):
        key = _get_key(view_tuples[0])
        view_collection[key].name = "foo"
        view_collection.refresh()
        assert view_collection[key].name == view_tuples[0].name
        assert len(view_collection[key]._changes) == 0

    def test_refresh_populates_collection(self, view_collection, view_tuples):
        """refresh() populates collection with View objects from provider data."""
        for result in view_collection:
            assert isinstance(result, objects.View)

    def test_all_views_present(self, view_tuples, view_collection):
        """All views from provider are present in the collection."""
        for v in view_tuples:
            key = _get_key(v)
            assert key in view_collection

    def test_metadata_mapping(self, view_tuples, view_collection):
        """All metadata fields are correctly mapped to View objects."""
        for v in view_tuples:
            key = _get_key(v)
            result = view_collection[key]
            assert result.name == v.name
            assert result.owner == v.owner
            assert result.schema == v.schema
            assert result.oid == v.oid

    def test_refresh_calls_provider(self, view_collection, mock_provider):
        """refresh() calls provider.get_views() each time."""
        call_count_before = mock_provider.get_views.call_count
        view_collection.refresh()
        assert mock_provider.get_views.call_count == call_count_before + 1

    def test_schema_filtering(self, cluster_with_mock_provider, mock_provider, view_tuples):
        """Schema filter is passed through to provider.get_views()."""
        schema = "public"
        filtered = [v for v in _view_tuples_to_dicts(view_tuples) if v["schema"] == schema]
        mock_provider.get_views.return_value = filtered
        collection = objects.ViewCollection(cluster=cluster_with_mock_provider, schema=schema)
        mock_provider.get_views.assert_called_with(schema)
        for result in collection:
            assert result.schema == schema

    def test_empty_results(self, cluster_with_mock_provider, mock_provider):
        """Empty provider results produce an empty collection."""
        mock_provider.get_views.return_value = []
        collection = objects.ViewCollection(cluster=cluster_with_mock_provider)
        assert len(collection) == 0

    def test_provider_attribute_set(self, cluster_with_mock_provider, mock_provider):
        """ViewCollection stores the provider from cluster.metadata_provider."""
        collection = objects.ViewCollection(cluster=cluster_with_mock_provider)
        assert collection.provider is mock_provider
