import pytest
from pgmob import objects


@pytest.fixture
def schema_cursor(cursor, schema_tuples):
    """Cursor that returns schema tuples"""
    cursor.fetchall.return_value = schema_tuples
    return cursor


@pytest.fixture
def schema_collection(cluster, schema_cursor):
    """Returns an initialized SchemaCollection object"""
    collection = objects.SchemaCollection(cluster=cluster)
    return collection


@pytest.fixture
def schema(cluster, schema_tuples):
    """Returns an initialized Schema object"""
    data = schema_tuples[0]
    obj = objects.Schema(
        cluster=cluster,
        name=data.nspname,
        owner=data.nspowner,
        oid=data.oid,
    )
    return obj


class TestSchemas:
    def test_init(self, schema_tuples, schema: objects.Schema):
        schema_data = schema_tuples[0]
        assert schema.name == schema_data.nspname
        assert schema.owner == schema_data.nspowner
        assert schema.oid == schema_data.oid
        assert str(schema) == f"Schema('{schema_data.nspname}')"

    def test_drop(self, schema: objects.Schema, cursor, pgmob_tester):
        schema.drop()
        pgmob_tester.assertSql("DROP SCHEMA", cursor)

    def test_drop_cascade(self, schema: objects.Schema, cursor, pgmob_tester):
        schema.drop(cascade=True)
        pgmob_tester.assertSql("DROP SCHEMA", cursor)
        pgmob_tester.assertSql("CASCADE", cursor)

    def test_refresh(self, schema: objects.Schema, schema_cursor, schema_tuples):
        tpl = schema_tuples[0]
        schema.owner = "foo"
        schema.refresh()
        assert schema.name == tpl.nspname
        assert schema.owner == tpl.nspowner
        assert schema.oid == tpl.oid

    def test_alter(self, schema: objects.Schema, schema_cursor, pgmob_tester):
        schema.name = "bar"
        schema.owner = "foo"
        schema.alter()
        pgmob_tester.assertSql("ALTER SCHEMA", schema_cursor)
        pgmob_tester.assertSql(" OWNER TO ", schema_cursor)
        pgmob_tester.assertSql(" RENAME TO ", schema_cursor)

    def test_create(self, schema: objects.Schema, schema_cursor, pgmob_tester):
        schema.create()
        pgmob_tester.assertSql("CREATE SCHEMA", schema_cursor)

    def test_script(self, schema: objects.Schema, cursor, pgmob_tester):
        cursor.mogrify.return_value = "foo"
        assert schema.script() == "foo"
        pgmob_tester.assertSql("CREATE SCHEMA", cursor, mogrify=True)


class TestSchemaCollection:
    def test_init(self, schema_tuples, schema_collection):
        for result in schema_collection:
            assert isinstance(result, objects.Schema)
        for schema_data in schema_tuples:
            result = schema_collection[schema_data.nspname]
            assert result.name == schema_data.nspname
            assert result.owner == schema_data.nspowner
            assert result.oid == schema_data.oid
            assert str(result) == f"Schema('{schema_data.nspname}')"

    def test_refresh(self, schema_collection: objects.SchemaCollection, schema_tuples):
        schema_collection[schema_tuples[0].nspname].name = "foo"
        schema_collection.refresh()
        assert schema_collection[schema_tuples[0].nspname].name == schema_tuples[0].nspname
        assert len(schema_collection[schema_tuples[0].nspname]._changes) == 0

    def test_new(self, schema_collection: objects.SchemaCollection):
        result = schema_collection.new(name="foo", owner="bar")
        assert result.name == "foo"
        assert result.owner == "bar"
        assert result.oid is None
        assert result.parent == schema_collection
        assert result.cluster == schema_collection.cluster

    def test_add(self, schema_collection: objects.SchemaCollection, cursor):
        cursor.fetchall.return_value = [("foo", "bar", 123)]
        schema = objects.Schema(name="foo", owner="bar")
        schema_collection.add(schema)
        result = schema_collection["foo"]
        assert result.name == "foo"
        assert result.owner == "bar"
        assert result.oid == 123
        assert result.parent == schema_collection
        assert result.cluster == schema_collection.cluster
