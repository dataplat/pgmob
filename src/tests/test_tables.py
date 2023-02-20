from unittest.mock import call
import pytest
from pgmob.sql import SQL, Identifier
from pgmob import objects


@pytest.fixture
def table_cursor(cursor, table_tuples):
    """Cursor that returns table tuples"""
    cursor.fetchall.return_value = table_tuples
    return cursor


@pytest.fixture
def table_collection(cluster, table_cursor):
    """Returns an initialized TableCollection object"""
    collection = objects.TableCollection(cluster=cluster)
    return collection


@pytest.fixture
def table(cluster, table_tuples):
    """Returns an initialized Table object"""
    data = table_tuples[0]
    return objects.Table(
        cluster=cluster,
        name=data.tablename,
        owner=data.tableowner,
        schema=data.schemaname,
        oid=data.oid,
    )


def _get_key(table):
    return table.tablename if table.schemaname == "public" else f"{table.schemaname}.{table.tablename}"


class TestTable:
    def test_init(self, table_tuples, table):
        tbl = table_tuples[0]
        assert table.name == tbl[0]
        assert table.owner == tbl[1]
        assert table.schema == tbl[2]
        assert table.tablespace is None
        assert table.row_security == False
        assert table.oid == tbl[5]
        assert str(table) == f"Table('{_get_key(tbl)}')"

    def test_drop(self, cursor, table, pgmob_tester):
        table.drop()
        pgmob_tester.assertSql(f"DROP TABLE ", cursor)
        pgmob_tester.assertSql(table.name, cursor)
        pgmob_tester.assertSql(table.schema, cursor)

    def test_drop_cascade(self, cursor, table, pgmob_tester):
        table.drop(True)
        pgmob_tester.assertSql(f"DROP TABLE ", cursor)
        pgmob_tester.assertSql(table.name, cursor)
        pgmob_tester.assertSql(table.schema, cursor)
        pgmob_tester.assertSql(f" CASCADE", cursor)

    def test_refresh(self, table, table_cursor, table_tuples, pgmob_tester):
        tbl = table_tuples[0]
        table.schema = "foo"
        table.refresh()
        assert table.name == tbl[0]
        assert table.owner == tbl[1]
        assert table.schema == tbl[2]
        assert table.tablespace == tbl[3]
        assert table.row_security == tbl[4]
        assert table.oid == tbl[5]
        assert str(table) == f"Table('{_get_key(tbl)}')"
        pgmob_tester.assertSql("FROM pg_catalog.pg_tables", table_cursor)

    def test_alter(self, table, table_cursor, table_tuples):
        src = table_tuples[0]
        table_cursor.fetchall.return_value = [src]
        fqn = SQL(".").join([Identifier(src.schemaname), Identifier(src.tablename)])
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


class TestTableCollection:
    def test_init(self, table_tuples, table_collection):
        for result in table_collection:
            assert isinstance(result, objects.Table)
        for tbl in table_tuples:
            key = _get_key(tbl)
            result = table_collection[key]
            assert result.name == tbl[0]
            assert result.owner == tbl[1]
            assert result.schema == tbl[2]
            assert result.tablespace == tbl[3]
            assert result.row_security == tbl[4]
            assert result.oid == tbl[5]
            assert str(result) == f"Table('{key}')"

    def test_refresh(self, table_collection: objects.TableCollection, table_tuples):
        key = _get_key(table_tuples[0])
        table_collection[key].name = "foo"
        table_collection.refresh()
        assert table_collection[key].name == table_tuples[0].tablename
        assert len(table_collection[key]._changes) == 0
