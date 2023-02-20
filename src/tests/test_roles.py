import pytest
from pgmob import objects


@pytest.fixture
def role_cursor(cursor, role_tuples):
    """Cursor that returns role tuples"""
    cursor.fetchall.return_value = role_tuples
    return cursor


@pytest.fixture
def role_collection(cluster, role_cursor):
    """Returns an initialized RoleCollection object"""
    collection = objects.RoleCollection(cluster=cluster)
    return collection


@pytest.fixture
def role(cluster, role_tuples):
    """Returns an initialized Role object"""
    data = role_tuples[0]
    obj = objects.Role(
        cluster=cluster,
        name=data.rolname,
        superuser=data.rolsuper,
        oid=data.oid,
    )
    return obj


class TestRole:
    def test_init(self, role: objects.Role, role_tuples):
        data = role_tuples[0]
        assert role.name == data.rolname
        assert role.superuser == data.rolsuper
        assert role.inherit == True
        assert role.createrole == False
        assert role.createdb == False
        assert role.login == False
        assert role.replication == False
        assert role.bypassrls == False
        assert role.connection_limit == -1
        assert role.valid_until is None
        assert role.oid == data.oid
        assert str(role) == f"Role('{data.rolname}')"

    def test_drop(self, role: objects.Role, cursor, pgmob_tester):
        role.drop()
        pgmob_tester.assertSql("DROP ROLE", cursor)

    def test_get_password_md5(self, role: objects.Role, cursor, pgmob_tester):
        cursor.fetchall.return_value = [("mockpassword",)]
        assert role.get_password_md5() == "mockpassword"
        pgmob_tester.assertSql("SELECT rolpassword FROM pg_catalog.pg_authid", cursor)

    def test_refresh(self, role: objects.Role, role_cursor, role_tuples):
        data = role_tuples[0]
        role.superuser = not data.rolsuper
        role.refresh()
        assert role.superuser == data.rolsuper
        assert role.inherit == data.rolinherit
        assert role.createrole == data.rolcreaterole
        assert role.createdb == data.rolcreatedb
        assert role.login == data.rolcanlogin
        assert role.replication == data.rolreplication
        assert role.bypassrls == data.rolbypassrls
        assert role.connection_limit == data.rolconnlimit
        assert role.valid_until == data.rolvaliduntil
        assert role.oid == data.oid

    def test_alter(self, role: objects.Role, role_cursor, role_tuples, pgmob_tester):
        role.name = "foo"
        role.inherit = False
        role.alter()
        pgmob_tester.assertSql("ALTER ROLE", role_cursor)
        pgmob_tester.assertSql(" RENAME TO ", role_cursor)
        pgmob_tester.assertSql(" NOINHERIT", role_cursor)

    def test_create(self, role: objects.Role, role_cursor, pgmob_tester):
        role.create()
        pgmob_tester.assertSql("CREATE ROLE", role_cursor)

    def test_script(self, role: objects.Role, cursor, pgmob_tester):
        cursor.fetchall.return_value = [("mockpassword",)]
        cursor.mogrify.return_value = "foo"
        assert role.script() == "foo"
        pgmob_tester.assertSql("CREATE ROLE", cursor, mogrify=True)

    def test_change_password(self, role: objects.Role, cursor, pgmob_tester):
        role.change_password("foobar")
        pgmob_tester.assertSql("ALTER ROLE", cursor)
        pgmob_tester.assertSql("PASSWORD", cursor)


class TestRoleCollection:
    def test_init(self, role_tuples, role_collection):
        for result in role_collection:
            assert isinstance(result, objects.Role)
        for role in role_tuples:
            result = role_collection[role[0]]
            assert result.name == role[0]
            assert result.superuser == role[1]
            assert result.inherit == role[2]
            assert result.createrole == role[3]
            assert result.createdb == role[4]
            assert result.login == role[5]
            assert result.replication == role[6]
            assert result.connection_limit == role[7]
            assert result.valid_until == role[8]
            assert result.bypassrls == role[9]
            assert result.oid == role[10]

    def test_refresh(self, role_collection: objects.RoleCollection, role_tuples):
        role_collection[role_tuples[0].rolname].name = "foo"
        role_collection.refresh()
        assert role_collection[role_tuples[0].rolname].name == role_tuples[0].rolname
        assert len(role_collection[role_tuples[0].rolname]._changes) == 0

    def test_new(self, role_collection: objects.RoleCollection):
        result = role_collection.new(name="foo", superuser=True)
        assert result.name == "foo"
        assert result.superuser == True
        assert result.oid is None
        assert result.parent == role_collection
        assert result.cluster == role_collection.cluster

    def test_add(self, role_collection: objects.RoleCollection, cursor):
        cursor.fetchall.return_value = [
            (
                "foo",
                True,
                True,
                False,
                False,
                False,
                False,
                -1,
                None,
                False,
                123,
            )
        ]
        role = objects.Role(name="foo", superuser=True)
        role_collection.add(role)
        result = role_collection["foo"]
        assert result.name == "foo"
        assert result.superuser == True
        assert result.oid == 123
        assert result.parent == role_collection
        assert result.cluster == role_collection.cluster
