import pytest

from pgmob import objects


@pytest.fixture
def databases(cluster, db):
    yield objects.DatabaseCollection(cluster=cluster)


class TestFunctionalDatabase:
    database_query = (
        "SELECT {field} FROM pg_catalog.pg_database d"
        " JOIN pg_catalog.pg_roles r on d.datdba = r.oid"
        " WHERE d.datname = '{db}'"
    )

    def test_init(self, db, databases: objects.DatabaseCollection):
        collation = "en_US.utf8"
        db_item = databases[db]
        assert db_item.name == db
        assert db_item.owner == "postgres"
        assert db_item.encoding == "UTF8"
        assert db_item.collation == collation
        assert db_item.character_type == collation
        assert db_item.allow_connections == True
        assert db_item.connection_limit == -1
        assert db_item.last_sys_oid is not None
        assert db_item.frozen_xid is not None
        assert db_item.min_multixact_id is not None
        assert db_item.tablespace is not None
        assert db_item.acl is None
        assert db_item.oid is not None and db_item.oid > 0
        assert str(db_item) == f"Database('{db}')"

    # setters
    def test_owner(self, db, databases: objects.DatabaseCollection, role, psql):
        db_obj = databases[db]
        db_obj.owner = role
        assert db_obj.owner == role
        assert psql(self.database_query.format(field="r.rolname", db=db)).output == "postgres"
        db_obj.alter()
        assert psql(self.database_query.format(field="r.rolname", db=db)).output == role
        assert db_obj.owner == role
        psql(f"DROP DATABASE {db}")

    def test_name(self, old_db, databases: objects.DatabaseCollection, psql, new_db):
        assert psql(f"DROP DATABASE {new_db}").exit_code == 0
        db_obj = databases[old_db]
        db_obj.name = "tmpdoittwice"
        db_obj.name = new_db
        assert db_obj.name == new_db
        assert psql(self.database_query.format(field="d.datname", db=old_db)).output == old_db
        db_obj.alter()
        assert db_obj.name == new_db
        databases.refresh()
        db_obj = databases[new_db]
        assert psql(self.database_query.format(field="d.datname", db=new_db)).output == new_db
        assert db_obj.name == new_db

    # methods
    def test_create(self, role, db, databases: objects.DatabaseCollection, psql):
        psql(f"DROP DATABASE {db}")
        db_obj = databases.new(name=db, owner=role, template="template0", is_template=False)
        db_obj.create()
        assert db_obj.oid is not None and db_obj.oid > 0
        assert psql(self.database_query.format(field="r.rolname", db=db)).output == role

    def test_script(self, db, databases: objects.DatabaseCollection, psql):
        db_obj = databases[db]
        assert (
            db_obj.script()
            == b"CREATE DATABASE \"pgmobtest\" OWNER \"postgres\" ENCODING 'UTF8' LC_COLLATE 'en_US.utf8' LC_CTYPE 'en_US.utf8'"
        )
