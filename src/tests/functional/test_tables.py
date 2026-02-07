import pytest

from pgmob import objects


@pytest.fixture
def tables(psql, db, cluster_db, schema):
    """Creates a set of tables"""
    table_list = [
        "public.tmpzzz",
        f"{schema}.tmpzzz",
        "public.tmpyyy",
        "public.tmprename",
    ]
    for t in table_list:
        psql(f"CREATE TABLE {t} (a int GENERATED ALWAYS AS IDENTITY)", db=db)

    tables = objects.TableCollection(cluster=cluster_db)
    yield tables


class TestTables:
    table_query = (
        "SELECT {field} FROM pg_catalog.pg_tables WHERE tablename = '{name}' AND schemaname = '{schema}'"
    )

    def test_init(self, tables):
        tbl = tables["tmpzzz"]
        assert tbl.name == "tmpzzz"
        assert tbl.owner == "postgres"
        assert tbl.schema == "public"
        assert tbl.tablespace is None
        assert tbl.row_security == False
        assert tbl.oid > 0

        tbl = tables["tmp.tmpzzz"]
        assert tbl.name == "tmpzzz"
        assert tbl.owner == "postgres"
        assert tbl.schema == "tmp"
        assert tbl.tablespace is None
        assert tbl.row_security == False
        assert tbl.oid > 0

    def test_owner(self, tables, role, psql, db):
        def get_current():
            return psql(
                self.table_query.format(field="tableowner", name="tmpzzz", schema="public"),
                db=db,
            ).output

        tbl = tables["tmpzzz"]
        tbl.owner = role
        assert tbl.owner == role
        assert get_current() == "postgres"
        tbl.alter()
        assert get_current() == role
        assert tbl.owner == role
        assert psql("DROP TABLE tmpzzz", db=db).exit_code == 0

    def test_tablespace(self, tables, psql, db, tablespace):
        def get_current():
            return psql(
                self.table_query.format(field="tablespace", name="tmpzzz", schema="public"),
                db=db,
            ).output

        tbl = tables["tmpzzz"]
        tbl.tablespace = tablespace
        assert tbl.tablespace == tablespace
        assert get_current() == ""
        tbl.alter()
        assert get_current() == tablespace
        assert tbl.tablespace == tablespace
        assert psql("DROP TABLE tmpzzz", db=db).exit_code == 0

    def test_row_security(self, tables, psql, db):
        def get_current():
            return psql(
                self.table_query.format(field="rowsecurity", name="tmpzzz", schema="public"),
                db=db,
            ).output

        tbl = tables["tmpzzz"]
        tbl.row_security = True
        assert tbl.row_security == True
        assert get_current() == "f"
        tbl.alter()
        assert tbl.row_security == True
        assert get_current() == "t"

    def test_schema(self, tables, psql, db, schema):
        def get_current(schema="public"):
            return psql(
                self.table_query.format(field="schemaname", name="tmpyyy", schema=schema),
                db=db,
            ).output

        tbl = tables["tmpyyy"]
        tbl.schema = "tmpdoittwice"
        tbl.schema = schema
        assert tbl.schema == schema
        assert get_current() == "public"
        tbl.alter()
        tables.refresh()
        tbl = tables[f"{schema}.tmpyyy"]
        assert get_current(schema) == schema
        assert tbl.schema == schema

    def test_name(self, tables, psql, db):
        def get_current(name):
            return psql(
                self.table_query.format(field="tablename", name=name, schema="public"),
                db=db,
            ).output

        tbl = tables["tmprename"]
        tbl.name = "tmpdoittwice"
        tbl.name = "tmprenamed"
        assert tbl.name == "tmprenamed"
        assert get_current("tmprename") == "tmprename"
        tbl.alter()
        tables.refresh()
        tbl = tables["tmprenamed"]
        assert get_current("tmprenamed") == "tmprenamed"
        assert tbl.name == "tmprenamed"

    def test_drop(self, tables, psql, db, schema):
        def get_current(schema="public"):
            return psql(
                self.table_query.format(field="tablename", name="tmpzzz", schema=schema),
                db=db,
            ).output

        tables["tmpzzz"].drop()
        assert get_current() == ""
        tables[f"{schema}.tmpzzz"].drop(cascade=True)
        assert get_current(schema) == ""
