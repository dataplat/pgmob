import pytest
from pgmob import objects


@pytest.fixture
def views(psql, db, cluster_db, schema):
    """Creates a set of views"""
    view_list = ["public.tmpzzz", f"{schema}.tmpzzz", "public.tmpyyy", "public.tmprename"]
    for v in view_list:
        psql(f"CREATE VIEW {v} AS (SELECT 1 as a)", db=db)
    views = objects.ViewCollection(cluster=cluster_db)
    yield views


class TestViews:
    view_query = "SELECT {field} FROM pg_views WHERE viewname = '{name}' AND schemaname = '{schema}'"

    def test_init(self, views):
        view = views["tmpzzz"]
        assert view.name == "tmpzzz"
        assert view.owner == "postgres"
        assert view.schema == "public"
        assert view.oid > 0

        view = views["tmp.tmpzzz"]
        assert view.name == "tmpzzz"
        assert view.owner == "postgres"
        assert view.schema == "tmp"
        assert view.oid > 0

    def test_owner(self, views, role, psql, db):
        def get_current():
            return psql(
                self.view_query.format(field="viewowner", name="tmpzzz", schema="public"),
                db=db,
            ).output

        view = views["tmpzzz"]
        view.owner = role
        assert view.owner == role
        assert get_current() == "postgres"
        view.alter()
        assert get_current() == role
        assert view.owner == role
        assert psql("DROP VIEW tmpzzz", db=db).exit_code == 0

    def test_schema(self, views, schema, psql, db):
        def get_current(schema="public"):
            return psql(
                self.view_query.format(field="schemaname", name="tmpyyy", schema=schema),
                db=db,
            ).output

        view = views["tmpyyy"]
        view.schema = "tmpdoittwice"
        view.schema = schema
        assert view.schema == schema
        assert get_current() == "public"
        view.alter()
        views.refresh()
        view = views[f"{schema}.tmpyyy"]
        assert get_current(schema) == schema
        assert view.schema == schema

    def test_name(self, views, psql, db):
        def get_current(name):
            return psql(
                self.view_query.format(field="viewname", name=name, schema="public"),
                db=db,
            ).output

        view = views["tmprename"]
        view.name = "tmpdoittwice"
        view.name = "tmprenamed"
        assert view.name == "tmprenamed"
        assert get_current("tmprename") == "tmprename"
        view.alter()
        views.refresh()
        view = views["tmprenamed"]
        assert get_current("tmprenamed") == "tmprenamed"
        assert view.name == "tmprenamed"

    def test_drop(self, views, psql, db, schema):
        def get_current(schema="public"):
            return psql(
                self.view_query.format(field="viewname", name="tmpzzz", schema=schema),
                db=db,
            ).output

        views["tmpzzz"].drop()
        assert get_current() == ""
        views[f"{schema}.tmpzzz"].drop(cascade=True)
        assert get_current(schema) == ""

        views.refresh()
        assert "tmpzzz" not in views
        assert f"{schema}.tmpzzz" not in views
