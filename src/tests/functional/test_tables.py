import pytest
from pgmob import objects


@pytest.fixture
def tables(psql, db, cluster_db, schema) -> objects.TableCollection:
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


@pytest.fixture
def columns(psql, db, cluster_db) -> objects.ColumnCollection:
    """Creates a set of columns"""
    column_data = [
        ("id", "int", "NOT NULL GENERATED ALWAYS AS IDENTITY"),
        ("name", "text", "COLLATE 'C' DEFAULT ('unknown')"),
        ("data", "jsonb", ""),
        ("limited", "varchar[32]", ""),
        ("arr", "int[]", ""),
        ("gen", "int", "GENERATED ALWAYS AS (id * 2) STORED NOT NULL"),
    ]
    table_name = "columnarium"
    definition = ""
    for name, typ, other in column_data:
        definition += ("," if definition else "") + f"{name} {typ} {other}"

    psql(f"CREATE TABLE {table_name} ({definition})", db=db)

    tables = objects.TableCollection(cluster=cluster_db)
    columns = objects.ColumnCollection(table=tables[table_name])
    yield columns


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
        assert "a" in tbl.columnns

        tbl = tables["tmp.tmpzzz"]
        assert tbl.name == "tmpzzz"
        assert tbl.owner == "postgres"
        assert tbl.schema == "tmp"
        assert tbl.tablespace is None
        assert tbl.row_security == False
        assert tbl.oid > 0
        assert "a" in tbl.columnns

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


class TestColumns:
    column_query = """SELECT {field}
FROM   pg_attribute a
JOIN pg_type t on t.oid = a.atttypid
LEFT JOIN pg_collation c on c.oid = a.attcollation
LEFT JOIN pg_attrdef d on a.atthasdef AND d.adrelid = a.attrelid AND a.attnum = d.adnum
WHERE  attrelid = 'columnarium'::regclass
AND    attnum > 0
AND    NOT attisdropped
AND    a.attname = '{name}'"""

    def get_current(self, psql, db, field, name):
        return psql(
            self.column_query.format(name=name, field=field),
            db=db,
        ).output

    def test_init(self, columns):
        col = columns["id"]
        assert col.name == "id"
        assert col.type == "int"  # TODO: change to proper type object once implemented
        assert col.stat_target == -1
        assert col.type_mod == -1
        assert col.number == 1
        assert col.nullable == False
        assert col.is_array == False
        assert col.default == False
        assert col.expression is None
        assert col.identity == "ALWAYS"
        assert col.generated is None
        assert col.collation is None

        col = columns["name"]
        assert col.name == "name"
        assert col.type == "text"
        assert col.stat_target == -1
        assert col.type_mod == -1
        assert col.number == 2
        assert col.nullable == True
        assert col.is_array == False
        assert col.default == True
        assert col.expression == "'unknown'"
        assert col.identity is None
        assert col.generated is None
        assert col.collation == "C"

        col = columns["data"]
        assert col.name == "data"
        assert col.type == "jsonb"
        assert col.stat_target == -1
        assert col.type_mod == -1
        assert col.number == 3
        assert col.nullable == True
        assert col.is_array == False
        assert col.default == False
        assert col.expression is None
        assert col.identity is None
        assert col.generated is None
        assert col.collation is None

        col = columns["limited"]
        assert col.name == "limited"
        assert col.type == "varchar"
        assert col.stat_target == -1
        assert col.type_mod == 32
        assert col.number == 4
        assert col.nullable == True
        assert col.is_array == False
        assert col.default == False
        assert col.expression is None
        assert col.identity is None
        assert col.generated is None
        assert col.collation is None

        col = columns["arr"]
        assert col.name == "arr"
        assert col.type == "int[]"
        assert col.stat_target == -1
        assert col.type_mod == -1
        assert col.number == 5
        assert col.nullable == True
        assert col.is_array == True
        assert col.default == False
        assert col.expression is None
        assert col.identity is None
        assert col.generated is None
        assert col.collation is None

        col = columns["gen"]
        assert col.name == "gen"
        assert col.type == "int"
        assert col.stat_target == -1
        assert col.type_mod == -1
        assert col.number == 6
        assert col.nullable == False
        assert col.is_array == False
        assert col.default == True
        assert col.expression == "id * 2"
        assert col.identity is None
        assert col.generated == "STORED"
        assert col.collation is None
