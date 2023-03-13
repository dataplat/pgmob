from typing import List, Any
from unittest.mock import MagicMock, call
import pytest
from pgmob.sql import SQL, Identifier
from pgmob import objects, Cluster
from .tuples import ColumnTuple, TableTuple
from .helpers import *


@pytest.fixture
def table_cursor(cursor: MagicMock, table_tuples: List[TableTuple]):
    """Cursor that returns table tuples"""
    cursor.fetchall.return_value = table_tuples
    return cursor


@pytest.fixture
def table_collection(cluster: Cluster, table_cursor: Any) -> objects.TableCollection:
    """Returns an initialized TableCollection object"""
    collection = objects.TableCollection(cluster=cluster)
    return collection


@pytest.fixture
def table(cluster: Cluster, table_tuples: list[TableTuple]) -> objects.Table:
    """Returns an initialized Table object"""
    data = table_tuples[0]
    return objects.Table(
        cluster=cluster,
        name=data.tablename,
        owner=data.tableowner,
        schema=data.schemaname,
        oid=data.oid,
    )


@pytest.fixture
def column_cursor(cursor: Any, column_tuples: List[ColumnTuple]) -> MagicMock:
    """Cursor that returns column tuples"""
    cursor.fetchall.return_value = column_tuples
    return cursor


@pytest.fixture
def column_collection(cluster: Cluster, column_cursor: Any, table: objects.Table) -> objects.ColumnCollection:
    """Returns an initialized ColumnCollection object"""
    collection = objects.ColumnCollection(cluster=cluster, table=table)
    return collection


@pytest.fixture
def column(cluster: Cluster, column_tuples: List[ColumnTuple], table: objects.Table) -> objects.Column:
    """Returns an initialized Column object"""
    data = column_tuples[0]
    return objects.Column(
        cluster=cluster,
        name=data.attname,
        table=table,
        type=data.type,
        number=1,
    )


def _get_key(table: TableTuple) -> str:
    return table.tablename if table.schemaname == "public" else f"{table.schemaname}.{table.tablename}"


class TestTable:
    def test_init(self, table_tuples: list[TableTuple], table: objects.Table):
        tbl = table_tuples[0]
        assert table.name == tbl[0]
        assert table.owner == tbl[1]
        assert table.schema == tbl[2]
        assert table.tablespace is None
        assert table.row_security == False
        assert table.oid == tbl[5]
        assert str(table) == f"Table('{_get_key(tbl)}')"

    def test_drop(self, cursor: Any, table: objects.Table, pgmob_tester: PGMobTester):
        table.drop()
        pgmob_tester.assertSql(f"DROP TABLE ", cursor)
        pgmob_tester.assertSql(table.name, cursor)
        pgmob_tester.assertSql(table.schema, cursor)

    def test_drop_cascade(self, cursor: Any, table: objects.Table, pgmob_tester: PGMobTester):
        table.drop(True)
        pgmob_tester.assertSql(f"DROP TABLE ", cursor)
        pgmob_tester.assertSql(table.name, cursor)
        pgmob_tester.assertSql(table.schema, cursor)
        pgmob_tester.assertSql(f" CASCADE", cursor)

    def test_refresh(
        self,
        table: objects.Table,
        table_cursor: Any,
        table_tuples: list[TableTuple],
        pgmob_tester: PGMobTester,
    ):
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

    def test_alter(self, table: objects.Table, table_cursor: Any, table_tuples: list[TableTuple]):
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
    def test_init(self, table_tuples: list[TableTuple], table_collection: objects.TableCollection):
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

    def test_refresh(self, table_collection: objects.TableCollection, table_tuples: list[TableTuple]):
        key = _get_key(table_tuples[0])
        table_collection[key].name = "foo"
        table_collection.refresh()
        assert table_collection[key].name == table_tuples[0].tablename
        assert len(table_collection[key]._changes) == 0


class TestColumn:
    def test_init(self, column_tuples: List[ColumnTuple], column: objects.Column):
        col = column_tuples[0]
        assert column.name == col.attname
        assert column.type == col.type
        assert column.stat_target == -1
        assert column.type_mod is None
        assert column.number == 1
        assert column.nullable == True
        assert column.is_array == False
        assert column.has_default == False
        assert column.expression is None
        assert column.identity == objects.Identity.NOT_GENERATED
        assert column.generated == objects.GeneratedColumn.NOT_GENERATED
        assert column.collation is None
        assert str(column) == f"Column('{col.attname}')"

    def test_refresh(
        self,
        column_tuples: List[ColumnTuple],
        column: objects.Column,
        column_cursor: MagicMock,
        pgmob_tester: PGMobTester,
    ):
        col = column_tuples[0]
        column.name = "foo"
        column.refresh()
        assert column.name == col.attname
        pgmob_tester.assertSql("FROM pg_catalog.pg_attribute", column_cursor)

    def test_alter(
        self,
        column: objects.Column,
        column_cursor: MagicMock,
        pgmob_tester: PGMobTester,
    ):
        column.name = "foo"
        column.alter()
        pgmob_tester.assertSql("ALTER TABLE", column_cursor)
        pgmob_tester.assertSql(" RENAME COLUMN ", column_cursor)
        pgmob_tester.assertSql("foo", column_cursor)


class TestColumnCollection:
    def test_init(self, column_tuples: List[ColumnTuple], column_collection: objects.ColumnCollection):
        for result in column_collection:
            assert isinstance(result, objects.Column)
        for col in column_tuples:
            column = column_collection[col.attname]
            assert column.name == col.attname
            assert column.type == col.type
            assert column.stat_target == col.attstattarget
            assert column.type_mod == col.type_mod
            assert column.number == col.attnum
            assert column.nullable == col.nullable
            assert column.is_array == col.is_array
            assert column.has_default == col.atthasdef
            assert column.expression == col.expr
            assert isinstance(column.identity, objects.Identity)
            assert isinstance(column.generated, objects.GeneratedColumn)
            assert column.collation == col.collname

    def test_refresh(self, column_collection: objects.ColumnCollection, column_tuples: List[ColumnTuple]):
        key = column_tuples[0].attname
        column_collection[key].name = "foo"
        column_collection.refresh()
        assert column_collection[key].name == column_tuples[0].attname
        assert len(column_collection[key]._changes) == 0
