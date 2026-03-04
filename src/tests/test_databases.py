from unittest.mock import call

import pytest

from pgmob import objects
from pgmob.sql import SQL, Identifier


def _db_tuples_to_dicts(db_tuples):
    """Convert database namedtuples to provider-style dicts."""
    return [
        {
            "name": d.name,
            "owner": d.owner,
            "encoding": d.encoding,
            "collation": d.collation,
            "character_type": d.character_type,
            "is_template": d.is_template,
            "allow_connections": d.allow_connections,
            "connection_limit": d.connection_limit,
            "last_sys_oid": d.last_sys_oid,
            "frozen_xid": d.frozen_xid,
            "min_multixact_id": d.min_multixact_id,
            "tablespace": d.tablespace,
            "acl": d.acl,
            "oid": d.oid,
        }
        for d in db_tuples
    ]


@pytest.fixture
def mock_provider(mocker, db_tuples):
    """Mock metadata provider that returns db_tuples data."""
    provider = mocker.Mock()
    provider.get_databases.return_value = _db_tuples_to_dicts(db_tuples)
    return provider


@pytest.fixture
def cluster_with_mock_provider(cluster, mock_provider):
    """Cluster with metadata_provider replaced by a mock."""
    cluster.metadata_provider = mock_provider
    return cluster


@pytest.fixture
def db_cursor(cursor, db_tuples):
    """Cursor that returns db tuples"""
    cursor.fetchall.return_value = db_tuples
    return cursor


@pytest.fixture
def database_collection(cluster_with_mock_provider):
    """Returns an initialized DatabaseCollection object using mock provider."""
    collection = objects.DatabaseCollection(cluster=cluster_with_mock_provider)
    return collection


@pytest.fixture
def database(cluster, db_tuples):
    """Returns an initialized Database object"""
    db_data = db_tuples[0]
    collection = objects.Database(
        cluster=cluster,
        name=db_data.name,
        owner=db_data.owner,
        encoding=db_data.encoding,
        collation=db_data.collation,
        is_template=db_data.is_template,
        oid=db_data.oid,
    )
    return collection


class TestDatabase:
    def test_init(self, database: objects.Database, db_tuples):
        db = db_tuples[0]
        assert database.name == db.name
        assert database.owner == db.owner
        assert database.encoding == db.encoding
        assert database.collation == db.collation
        assert database.is_template == db.is_template
        assert database.character_type == None
        assert database.allow_connections == True
        assert database.connection_limit is None
        assert database.last_sys_oid is None
        assert database.frozen_xid is None
        assert database.min_multixact_id is None
        assert database.tablespace is None
        assert database.acl is None
        assert database.oid == db.oid
        assert str(database) == f"Database('{db.name}')"

    def test_drop(self, database: objects.Database, cursor):
        database.drop()
        assert cursor.execute.call_args_list[1].args[0]._parts[0]._value.strip() == "DROP DATABASE"

    def test_refresh(self, database: objects.Database, db_cursor, db_tuples):
        db = db_tuples[0]
        database.owner = "foo"
        database.refresh()
        assert database.name == db.name
        assert database.owner == db.owner
        assert database.encoding == db.encoding
        assert database.collation == db.collation
        assert database.character_type == db.character_type
        assert database.is_template == db.is_template
        assert database.allow_connections == db.allow_connections
        assert database.connection_limit == db.connection_limit
        assert database.last_sys_oid == db.last_sys_oid
        assert database.frozen_xid == db.frozen_xid
        assert database.min_multixact_id == db.min_multixact_id
        assert database.tablespace == db.tablespace
        assert database.acl == db.acl
        assert database.oid == db.oid
        assert str(database) == f"Database('{db.name}')"

    def test_alter(self, database: objects.Database, db_cursor, db_tuples):
        database.owner = "foo"
        database.name = "bar"
        database.tablespace = "tbs1"
        database.alter()
        db_cursor.execute.assert_has_calls(
            [
                call(
                    SQL("ALTER DATABASE {db} OWNER TO {new}").format(
                        db=Identifier(db_tuples[0].name), new=Identifier("foo")
                    ),
                    None,
                ),
                call(
                    SQL("ALTER DATABASE {old} SET TABLESPACE {new}").format(
                        old=Identifier(db_tuples[0].name), new=Identifier("tbs1")
                    ),
                    None,
                ),
                call(
                    SQL("ALTER DATABASE {old} RENAME TO {new}").format(
                        old=Identifier(db_tuples[0].name), new=Identifier("bar")
                    ),
                    None,
                ),
            ]
        )

    def test_disable(self, database, cursor, pgmob_tester):
        database.disable()
        pgmob_tester.assertSql("UPDATE", cursor, statement=1)
        pgmob_tester.assertSql("False", cursor, statement=4)

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
            result = database_collection[db.name]
            assert result.name == db.name
            assert result.owner == db.owner
            assert result.parent == database_collection

    def test_refresh(self, database_collection: objects.DatabaseCollection, db_tuples):
        database_collection[db_tuples[0].name].owner = "foo"
        database_collection.refresh()
        assert database_collection[db_tuples[0].name].owner == db_tuples[0].owner
        assert len(database_collection[db_tuples[0].name]._changes) == 0

    def test_init_populates_collection(self, database_collection, db_tuples):
        """refresh() populates collection with Database objects from provider data."""
        for result in database_collection:
            assert isinstance(result, objects.Database)

    def test_init_all_databases_present(self, database_collection, db_tuples):
        """All databases from provider are present in the collection."""
        for db in db_tuples:
            assert db.name in database_collection

    def test_metadata_mapping(self, database_collection, db_tuples):
        """All metadata fields are correctly mapped to Database objects."""
        for db in db_tuples:
            result = database_collection[db.name]
            assert result.name == db.name
            assert result.owner == db.owner
            assert result.encoding == db.encoding
            assert result.collation == db.collation
            assert result.character_type == db.character_type
            assert result.is_template == db.is_template
            assert result.allow_connections == db.allow_connections
            assert result.connection_limit == db.connection_limit
            assert result.last_sys_oid == db.last_sys_oid
            assert result.frozen_xid == db.frozen_xid
            assert result.min_multixact_id == db.min_multixact_id
            assert result.tablespace == db.tablespace
            assert result.acl == db.acl
            assert result.oid == db.oid

    def test_refresh_repopulates_collection(self, database_collection, db_tuples, mock_provider):
        """refresh() clears and repopulates the collection."""
        database_collection[db_tuples[0].name].name = "foo"
        database_collection.refresh()
        assert database_collection[db_tuples[0].name].name == db_tuples[0].name
        assert len(database_collection[db_tuples[0].name]._changes) == 0

    def test_refresh_calls_provider(self, database_collection, mock_provider):
        """refresh() calls provider.get_databases() each time."""
        call_count_before = mock_provider.get_databases.call_count
        database_collection.refresh()
        assert mock_provider.get_databases.call_count == call_count_before + 1

    def test_empty_results(self, cluster_with_mock_provider, mock_provider):
        """Empty provider results produce an empty collection."""
        mock_provider.get_databases.return_value = []
        collection = objects.DatabaseCollection(cluster=cluster_with_mock_provider)
        assert len(collection) == 0

    def test_provider_attribute_set(self, cluster_with_mock_provider, mock_provider):
        """DatabaseCollection stores the provider from cluster.metadata_provider."""
        collection = objects.DatabaseCollection(cluster=cluster_with_mock_provider)
        assert collection.provider is mock_provider
