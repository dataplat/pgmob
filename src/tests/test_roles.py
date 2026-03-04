import pytest

from pgmob import objects


def _role_tuples_to_dicts(role_tuples):
    """Convert role namedtuples to provider-style dicts."""
    return [
        {
            "name": r.name,
            "superuser": r.superuser,
            "inherit": r.inherit,
            "createrole": r.createrole,
            "createdb": r.createdb,
            "login": r.login,
            "replication": r.replication,
            "connection_limit": r.connection_limit,
            "password": None,
            "valid_until": r.valid_until,
            "oid": r.oid,
        }
        for r in role_tuples
    ]


@pytest.fixture
def mock_provider(mocker, role_tuples):
    """Mock metadata provider that returns role_tuples data."""
    provider = mocker.Mock()
    provider.get_roles.return_value = _role_tuples_to_dicts(role_tuples)
    return provider


@pytest.fixture
def cluster_with_mock_provider(cluster, mock_provider):
    """Cluster with metadata_provider replaced by a mock."""
    cluster.metadata_provider = mock_provider
    return cluster


@pytest.fixture
def role_cursor(cursor, role_tuples):
    """Cursor that returns role tuples"""
    cursor.fetchall.return_value = role_tuples
    return cursor


@pytest.fixture
def role_collection(cluster_with_mock_provider):
    """Returns an initialized RoleCollection object using mock provider."""
    collection = objects.RoleCollection(cluster=cluster_with_mock_provider)
    return collection


@pytest.fixture
def role(cluster, role_tuples):
    """Returns an initialized Role object"""
    data = role_tuples[0]
    obj = objects.Role(
        cluster=cluster,
        name=data.name,
        superuser=data.superuser,
        oid=data.oid,
    )
    return obj


class TestRole:
    def test_init(self, role: objects.Role, role_tuples):
        data = role_tuples[0]
        assert role.name == data.name
        assert role.superuser == data.superuser
        assert role.inherit == True
        assert role.createrole == False
        assert role.createdb == False
        assert role.login == False
        assert role.replication == False
        assert role.bypassrls == False
        assert role.connection_limit == -1
        assert role.valid_until is None
        assert role.oid == data.oid
        assert str(role) == f"Role('{data.name}')"

    def test_drop(self, role: objects.Role, cursor, pgmob_tester):
        role.drop()
        pgmob_tester.assertSql("DROP ROLE", cursor)

    def test_get_password_md5(self, role: objects.Role, cursor, pgmob_tester):
        cursor.fetchall.return_value = [("mockpassword",)]
        assert role.get_password_md5() == "mockpassword"
        pgmob_tester.assertSql("SELECT rolpassword FROM pg_catalog.pg_authid", cursor)

    def test_refresh(self, role: objects.Role, role_cursor, role_tuples):
        data = role_tuples[0]
        role.superuser = not data.superuser
        role.refresh()
        assert role.superuser == data.superuser
        assert role.inherit == data.inherit
        assert role.createrole == data.createrole
        assert role.createdb == data.createdb
        assert role.login == data.login
        assert role.replication == data.replication
        assert role.bypassrls == data.bypassrls
        assert role.connection_limit == data.connection_limit
        assert role.valid_until == data.valid_until
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
    def test_init_populates_collection(self, role_tuples, role_collection):
        """refresh() populates collection with Role objects from provider data."""
        for result in role_collection:
            assert isinstance(result, objects.Role)

    def test_init_all_roles_present(self, role_tuples, role_collection):
        """All roles from provider are present in the collection."""
        for role in role_tuples:
            assert role.name in role_collection

    def test_metadata_mapping(self, role_tuples, role_collection):
        """All metadata fields are correctly mapped to Role objects."""
        for role in role_tuples:
            result = role_collection[role.name]
            assert result.name == role.name
            assert result.superuser == role.superuser
            assert result.inherit == role.inherit
            assert result.createrole == role.createrole
            assert result.createdb == role.createdb
            assert result.login == role.login
            assert result.replication == role.replication
            assert result.connection_limit == role.connection_limit
            assert result.valid_until == role.valid_until
            assert result.oid == role.oid

    def test_refresh_repopulates_collection(self, role_collection, role_tuples, mock_provider):
        """refresh() clears and repopulates the collection."""
        role_collection[role_tuples[0].name].name = "foo"
        role_collection.refresh()
        assert role_collection[role_tuples[0].name].name == role_tuples[0].name
        assert len(role_collection[role_tuples[0].name]._changes) == 0

    def test_refresh_calls_provider(self, role_collection, mock_provider):
        """refresh() calls provider.get_roles() each time."""
        call_count_before = mock_provider.get_roles.call_count
        role_collection.refresh()
        assert mock_provider.get_roles.call_count == call_count_before + 1

    def test_empty_results(self, cluster_with_mock_provider, mock_provider):
        """Empty provider results produce an empty collection."""
        mock_provider.get_roles.return_value = []
        collection = objects.RoleCollection(cluster=cluster_with_mock_provider)
        assert len(collection) == 0

    def test_provider_attribute_set(self, cluster_with_mock_provider, mock_provider):
        """RoleCollection stores the provider from cluster.metadata_provider."""
        collection = objects.RoleCollection(cluster=cluster_with_mock_provider)
        assert collection.provider is mock_provider

    def test_get_by_name_returns_role(self, role_tuples, role_collection, mock_provider):
        """get_by_name() returns a Role object with correct metadata."""
        role = role_tuples[1]
        mock_provider.get_role.return_value = {
            "name": role.name,
            "superuser": role.superuser,
            "inherit": role.inherit,
            "createrole": role.createrole,
            "createdb": role.createdb,
            "login": role.login,
            "replication": role.replication,
            "connection_limit": role.connection_limit,
            "password": None,
            "valid_until": role.valid_until,
            "oid": role.oid,
        }
        result = role_collection.get_by_name(role.name)
        assert result is not None
        assert isinstance(result, objects.Role)
        assert result.name == role.name
        assert result.superuser == role.superuser
        assert result.oid == role.oid
        mock_provider.get_role.assert_called_once_with(role.name)

    def test_get_by_name_not_found(self, role_collection, mock_provider):
        """get_by_name() returns None when provider returns None."""
        mock_provider.get_role.return_value = None
        result = role_collection.get_by_name("nonexistent")
        assert result is None

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
