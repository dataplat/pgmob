from unittest.mock import call

import pytest

from pgmob import objects
from pgmob.sql import SQL, Identifier


@pytest.fixture
def view_cursor(cursor, view_tuples):
    """Cursor that returns view tuples"""
    cursor.fetchall.return_value = view_tuples
    return cursor


@pytest.fixture
def view_collection(cluster, view_cursor):
    """Returns an initialized ViewCollection object"""
    collection = objects.ViewCollection(cluster=cluster)
    return collection


@pytest.fixture
def view(cluster, view_tuples):
    """Returns an initialized View object"""
    data = view_tuples[0]
    return objects.View(
        cluster=cluster,
        name=data.viewname,
        owner=data.viewowner,
        schema=data.schemaname,
        oid=data.oid,
    )


def _get_key(view):
    return view.viewname if view.schemaname == "public" else f"{view.schemaname}.{view.viewname}"


class TestView:
    def test_init(self, view_tuples, view):
        v = view_tuples[0]
        assert view.name == v[0]
        assert view.owner == v[1]
        assert view.schema == v[2]
        assert view.oid == v[3]
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
        assert view.name == v[0]
        assert view.owner == v[1]
        assert view.schema == v[2]
        assert view.oid == v[3]
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
            assert result.name == v[0]
            assert result.owner == v[1]
            assert result.schema == v[2]
            assert result.oid == v[3]
            assert str(result) == f"View('{key}')"

    def test_refresh(self, view_collection: objects.ViewCollection, view_tuples):
        key = _get_key(view_tuples[0])
        view_collection[key].name = "foo"
        view_collection.refresh()
        assert view_collection[key].name == view_tuples[0].viewname
        assert len(view_collection[key]._changes) == 0
