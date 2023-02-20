import pytest
from unittest.mock import call
from pgmob.sql import SQL, Identifier
from pgmob import objects


@pytest.fixture
def db_cursor(cursor, db_tuples):
    """Cursor that returns db tuples"""
    cursor.fetchall.return_value = db_tuples
    return cursor


@pytest.fixture
def database_collection(cluster, db_cursor):
    """Returns an initialized DatabaseCollection object"""
    # cursor.fetchall.return_value = db_cursor
    collection = objects.DatabaseCollection(cluster=cluster)
    return collection


@pytest.fixture
def database(cluster, db_tuples):
    """Returns an initialized Database object"""
    db_data = db_tuples[0]
    collection = objects.Database(
        cluster=cluster,
        name=db_data[0],
        owner=db_data[1],
        encoding=db_data[2],
        collation=db_data[3],
        is_template=db_data[5],
        oid=db_data.oid,
    )
    return collection


class TestDatabase:
    def test_init(self, database: objects.Database, db_tuples):
        db = db_tuples[0]
        assert database.name == db[0]
        assert database.owner == db[1]
        assert database.encoding == db[2]
        assert database.collation == db[3]
        assert database.is_template == db[5]
        assert database.character_type == None
        assert database.allow_connections == True
        assert database.connection_limit is None
        assert database.last_sys_oid is None
        assert database.frozen_xid is None
        assert database.min_multixact_id is None
        assert database.tablespace is None
        assert database.acl is None
        assert database.oid == db.oid
        assert str(database) == f"Database('{db[0]}')"

    def test_drop(self, database: objects.Database, cursor):
        database.drop()
        assert cursor.execute.call_args_list[1].args[0]._parts[0]._value.strip() == "DROP DATABASE"

    def test_refresh(self, database: objects.Database, db_cursor, db_tuples):
        db = db_tuples[0]
        database.owner = "foo"
        database.refresh()
        assert database.name == db[0]
        assert database.owner == db[1]
        assert database.encoding == db[2]
        assert database.collation == db[3]
        assert database.character_type == db[4]
        assert database.is_template == db[5]
        assert database.allow_connections == db[6]
        assert database.connection_limit == db[7]
        assert database.last_sys_oid == db[8]
        assert database.frozen_xid == db[9]
        assert database.min_multixact_id == db[10]
        assert database.tablespace == db[11]
        assert database.acl == db[12]
        assert database.oid == db[13]
        assert str(database) == f"Database('{db[0]}')"

    def test_alter(self, database: objects.Database, db_cursor, db_tuples):
        database.owner = "foo"
        database.name = "bar"
        database.tablespace = "tbs1"
        database.alter()
        db_cursor.execute.assert_has_calls(
            [
                call(
                    SQL("ALTER DATABASE {db} OWNER TO {new}").format(
                        db=Identifier(db_tuples[0].datname), new=Identifier("foo")
                    ),
                    None,
                ),
                call(
                    SQL("ALTER DATABASE {old} SET TABLESPACE {new}").format(
                        old=Identifier(db_tuples[0].datname), new=Identifier("tbs1")
                    ),
                    None,
                ),
                call(
                    SQL("ALTER DATABASE {old} RENAME TO {new}").format(
                        old=Identifier(db_tuples[0].datname), new=Identifier("bar")
                    ),
                    None,
                ),
            ]
        )

    def test_disable(self, database, cursor, pgmob_tester):
        database.disable()
        pgmob_tester.assertSql("UPDATE", cursor, statement=0)
        pgmob_tester.assertSql("False", cursor, statement=3)

    def test_create(self, database: objects.Database, db_cursor, pgmob_tester):
        database.create()
        pgmob_tester.assertSql("CREATE DATABASE", db_cursor)

    def test_script(self, database: objects.Database, cursor, pgmob_tester):
        cursor.mogrify.return_value = "foo"
        assert database.script() == "foo"
        pgmob_tester.assertSql("CREATE DATABASE", cursor, mogrify=True)


class TestDatabaseCollection:
    def test_init(self, database_collection: objects.DatabaseCollection, db_tuples):
        assert isinstance(database_collection, objects.DatabaseCollection)
        for result in database_collection:
            assert isinstance(result, objects.Database)
        for db in db_tuples:
            result = database_collection[db[0]]
            assert result.name == db[0]
            assert result.owner == db[1]
            assert result.parent == database_collection

    def test_refresh(self, database_collection: objects.DatabaseCollection, db_tuples):
        database_collection[db_tuples[0].datname].owner = "foo"
        database_collection.refresh()
        assert database_collection[db_tuples[0].datname].owner == db_tuples[0].datowner
        assert len(database_collection[db_tuples[0].datname]._changes) == 0
