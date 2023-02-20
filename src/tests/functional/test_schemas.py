import re
import pytest
from pgmob import objects


@pytest.fixture
def schemas(psql, db, cluster_db):
    """Creates a set of schemas"""
    schema_list = [
        "tmp",
        "tmp-2",
    ]
    for s in schema_list:
        psql(f'CREATE SCHEMA "{s}"', db=db)
    psql(f'CREATE TABLE "tmp-2".a (a int)', db=db)

    schemas = objects.SchemaCollection(cluster=cluster_db)
    yield schemas


class TestSchemas:
    schema_query = (
        "SELECT {field} "
        "FROM pg_catalog.pg_namespace n "
        "JOIN pg_catalog.pg_roles r on n.nspowner = r.oid "
        "WHERE n.nspname = '{schema}'"
    )

    def test_init(self, schemas):
        schema = schemas["tmp"]
        assert schema.name == "tmp"
        assert schema.owner == "postgres"
        assert schema.oid > 0

        schema = schemas["tmp-2"]
        assert schema.name == "tmp-2"
        assert schema.owner == "postgres"
        assert schema.oid > 0

    def test_owner(self, schemas, psql, db, role):
        def get_current():
            return psql(
                self.schema_query.format(field="r.rolname", schema="tmp"),
                db=db,
            ).output

        schema = schemas["tmp"]
        schema.owner = role
        assert get_current() == "postgres"
        schema.alter()
        assert get_current() == role
        assert schema.owner == role
        assert psql("DROP SCHEMA tmp CASCADE", db=db).exit_code == 0

    def test_name(self, schemas, psql, db):
        def get_current(schema):
            return psql(
                self.schema_query.format(field="n.nspname", schema=schema),
                db=db,
            ).output

        schema = schemas["tmp"]
        schema.name = "tmpdoittwice"
        schema.name = "tmprenamed"
        assert get_current("tmp") == "tmp"
        schema.alter()
        schemas.refresh()
        schema = schemas["tmprenamed"]
        assert get_current("tmprenamed") == "tmprenamed"
        assert schema.name == "tmprenamed"

    def test_drop(self, schemas, psql, db):
        def get_current(schema):
            return psql(
                self.schema_query.format(field="n.nspname", schema=schema),
                db=db,
            ).output

        assert get_current("tmp") == "tmp"
        assert get_current("tmp-2") == "tmp-2"
        schemas["tmp"].drop()
        assert get_current("tmp") == ""
        schemas["tmp-2"].drop(cascade=True)
        assert get_current("tmp-2") == ""

    def test_create(self, schemas: objects.SchemaCollection, db, role, psql):
        tmp_schema = schemas["tmp"].name
        assert psql(f"DROP SCHEMA {tmp_schema}", db=db).exit_code == 0
        schema_obj = schemas.new(name=tmp_schema, owner=role)
        schema_obj.create()
        assert schema_obj.oid > 0
        assert (
            psql(self.schema_query.format(field="n.nspname", schema=tmp_schema), db=db).output == tmp_schema
        )
        assert psql(self.schema_query.format(field="r.rolname", schema=tmp_schema), db=db).output == role
        assert psql(f"DROP SCHEMA {tmp_schema} CASCADE", db=db).exit_code == 0

    def test_script(self, schemas: objects.SchemaCollection):
        schema_obj = schemas["tmp"]
        assert re.match("CREATE SCHEMA.* AUTHORIZATION .*", schema_obj.script().decode("utf8"))
