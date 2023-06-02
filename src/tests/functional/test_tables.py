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
        ("name", "text", "COLLATE \"POSIX\" DEFAULT ('unknown')"),
        ("data", "jsonb", ""),
        ("limited", "varchar(30)", ""),
        ("arr", "int[]", ""),
        ("gen", "int", "GENERATED ALWAYS AS (id * 2) STORED NOT NULL"),
    ]
    table_name = "columnarium"
    definition = ""
    for name, typ, other in column_data:
        definition += ("," if definition else "") + f"{name} {typ} {other}"

    assert psql(f"CREATE TABLE {table_name} ({definition})", db=db).output == "CREATE TABLE"

    tables = objects.TableCollection(cluster=cluster_db)
    columns = objects.ColumnCollection(table=tables[table_name], cluster=cluster_db)
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
        assert "a" in tbl.columns

        tbl = tables["tmp.tmpzzz"]
        assert tbl.name == "tmpzzz"
        assert tbl.owner == "postgres"
        assert tbl.schema == "tmp"
        assert tbl.tablespace is None
        assert tbl.row_security == False
        assert tbl.oid > 0
        assert "a" in tbl.columns

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
        assert col.type == "integer"  # TODO: change to proper type object once implemented
        assert col.stat_target == -1
        assert col.type_mod is None
        assert col.number == 1
        assert col.nullable == False
        assert col.is_array == False
        assert col.has_default == False
        assert col.expression is None
        assert col.identity == objects.Identity.ALWAYS
        assert col.generated == objects.GeneratedColumn.NOT_GENERATED
        assert col.collation is None

        col = columns["name"]
        assert col.name == "name"
        assert col.type == "text"
        assert col.stat_target == -1
        assert col.type_mod is None
        assert col.number == 2
        assert col.nullable == True
        assert col.is_array == False
        assert col.has_default == True
        assert col.expression == "'unknown'::text"
        assert col.identity == objects.Identity.NOT_GENERATED
        assert col.generated == objects.GeneratedColumn.NOT_GENERATED
        assert col.collation == "POSIX"

        col = columns["data"]
        assert col.name == "data"
        assert col.type == "jsonb"
        assert col.stat_target == -1
        assert col.type_mod is None
        assert col.number == 3
        assert col.nullable == True
        assert col.is_array == False
        assert col.has_default == False
        assert col.expression is None
        assert col.identity == objects.Identity.NOT_GENERATED
        assert col.generated == objects.GeneratedColumn.NOT_GENERATED
        assert col.collation is None

        col = columns["limited"]
        assert col.name == "limited"
        assert col.type == "character varying(30)"
        assert col.stat_target == -1
        assert col.type_mod == 30
        assert col.number == 4
        assert col.nullable == True
        assert col.is_array == False
        assert col.has_default == False
        assert col.expression is None
        assert col.identity == objects.Identity.NOT_GENERATED
        assert col.generated == objects.GeneratedColumn.NOT_GENERATED
        assert col.collation == "default"

        col = columns["arr"]
        assert col.name == "arr"
        assert col.type == "integer[]"
        assert col.stat_target == -1
        assert col.type_mod is None
        assert col.number == 5
        assert col.nullable == True
        assert col.is_array == True
        assert col.has_default == False
        assert col.expression is None
        assert col.identity == objects.Identity.NOT_GENERATED
        assert col.generated == objects.GeneratedColumn.NOT_GENERATED
        assert col.collation is None

        col = columns["gen"]
        assert col.name == "gen"
        assert col.type == "integer"
        assert col.stat_target == -1
        assert col.type_mod is None
        assert col.number == 6
        assert col.nullable == False
        assert col.is_array == False
        assert col.has_default == True
        assert col.expression == "(id * 2)"
        assert col.identity == objects.Identity.NOT_GENERATED
        assert col.generated == objects.GeneratedColumn.STORED
        assert col.collation is None

        assert str(columns) == "ColumnCollection('id', 'name', 'data', 'limited', 'arr', 'gen')"

    def test_name(self, psql, db, columns: objects.ColumnCollection):
        col = columns["name"]
        col.name = "new_name"
        col.alter()
        assert self.get_current(psql, db, "attname", "new_name") == "new_name"

    def test_stat_target(self, psql, db, columns: objects.ColumnCollection):
        col = columns["name"]
        col.stat_target = 10
        col.alter()
        assert self.get_current(psql, db, "attstattarget", "name") == "10"

    def test_nullable(self, psql, db, columns: objects.ColumnCollection):
        col = columns["name"]
        col.nullable = False
        col.alter()
        assert self.get_current(psql, db, "attnotnull", "name") == "t"
        col.nullable = True
        col.alter()
        assert self.get_current(psql, db, "attnotnull", "name") == "f"

    def test_set_type(
        self,
        psql,
        db,
        columns: objects.ColumnCollection,
    ):
        col = columns["data"]
        for type, collation, using in [
            ("text", None, None),
            ("text", "POSIX", "data::text"),
            ("integer", None, "bit_length(data::text::bytea)"),
        ]:
            col.set_type(type=type, collation=collation, using=using)
            assert self.get_current(psql, db, "format_type(a.atttypid, a.atttypmod)", "data") == type
            assert self.get_current(psql, db, "c.collname", "data") == collation if collation else "default"
