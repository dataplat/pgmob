import doctest

import pytest

from pgmob import Cluster, objects, util
from pgmob.errors import PostgresShellCommandError


@pytest.fixture
def db_table_owner(psql, db, role):
    psql(f"ALTER DATABASE {db} OWNER TO {role}")
    psql(f"set role {role}; CREATE TABLE tmpzzz(a int)", db=db)
    yield role


class TestCluster:
    database_query = "SELECT datname from pg_database WHERE datname = '{db}'"
    role_query = "SELECT rolname, rolsuper, rolreplication ,rolcanlogin, rolconnlimit from pg_roles WHERE rolname = '{role}'"
    replication_slot_query = "SELECT slot_name, plugin from pg_replication_slots WHERE slot_name = '{slot}'"
    dat_owner_query = (
        "SELECT r.rolname FROM pg_catalog.pg_database d"
        " JOIN pg_catalog.pg_roles r on d.datdba = r.oid"
        " WHERE d.datname = '{db}'"
    )
    table_owner_query = (
        "SELECT tableowner FROM pg_tables WHERE tablename = '{name}' AND schemaname = '{schema}'"
    )

    def test_init(self, cluster: Cluster):
        assert cluster.adapter.connection is not None
        assert cluster.adapter.connection.__class__.__name__ == "connection"
        assert cluster.current_database == "postgres"
        assert cluster.version >= util.Version("10")

    def test_init_db(self, cluster_db: Cluster, db):
        assert cluster_db.adapter.connection is not None
        assert cluster_db.adapter.connection.__class__.__name__ == "connection"
        assert cluster_db.current_database == db
        assert cluster_db.version >= util.Version("10")

    def test_run_os_command_pwd(self, cluster: Cluster, psql):
        result = cluster.run_os_command("pwd").text
        assert result == psql("select setting from pg_settings where name = 'data_directory'").output

    def test_run_os_command_escape(self, cluster: Cluster):
        result = cluster.run_os_command('''echo "\\",'"''').text
        assert result == "\",'"
        result = cluster.run_os_command('''echo "'\\",\\"'"''').text
        assert result == "'\",\"'"

    def test_run_os_command_not_found(self, cluster: Cluster):
        cmd = "/bin/dsfsdf"
        with pytest.raises(
            PostgresShellCommandError,
            match="Error while executing shell command.*No such file or directory",
        ):
            cluster.run_os_command(cmd)
        result = cluster.run_os_command(cmd, raise_exception=False)
        assert result.exit_code == 127
        assert "No such file or directory" in result.text

    def test_run_os_command_failed(self, cluster: Cluster):
        cmd = "echo foo; /bin/false"
        with pytest.raises(PostgresShellCommandError, match="foo"):
            cluster.run_os_command(cmd)
        result = cluster.run_os_command(cmd, raise_exception=False)
        assert result.exit_code == 1
        assert result.text == "foo"

    def test_run_os_command_variables(self, cluster: Cluster):
        def test(cmd, result):
            assert cluster.run_os_command(cmd).text == result

        for x in [
            # escaped variable
            ("export whatisthisvar=foo; echo \\$whatisthisvar", "foo"),
            # variable substitutions
            ("echo $HOME", "/var/lib/postgresql"),
            ("echo $(whoami)", "postgres"),
        ]:
            test(*x)

    def test_execute(self, cluster: Cluster):
        def test(query, param, result):
            assert cluster.execute(query, param)[0] == result

        for x in [
            ("SELECT %s as s, %s as i", (5, "string"), (5, "string")),
            ("select current_database()", None, ("postgres",)),
            ("select current_user", None, ("postgres",)),
            # only returns results from the last query
            ("SELECT %s as s; SELECT %s as i", (5, "string"), ("string",)),
            (
                "SELECT a FROM generate_series(1, 5) as x(a) WHERE a IN %s",
                ((1, 2, 3),),
                (1,),
            ),
        ]:
            test(*x)

    def test_rename_database(self, cluster: Cluster, old_db, new_db, psql):
        psql(f"DROP DATABASE {new_db}")
        db = cluster.databases[old_db]
        db.name = new_db
        db.alter()
        assert psql(self.database_query.format(db=new_db)).output == new_db
        assert psql(self.database_query.format(db=old_db)).output == ""

    def test_create_database(self, cluster: Cluster, new_db, psql):
        psql(f"DROP DATABASE {new_db}")
        assert psql(self.database_query.format(db=new_db)).output == ""
        cluster.databases.new(name=new_db).create()
        assert psql(self.database_query.format(db=new_db)).output == new_db

    def test_drop_database(self, cluster: Cluster, new_db, psql):
        assert psql(self.database_query.format(db=new_db)).output == new_db
        cluster.databases[new_db].drop()
        assert psql(self.database_query.format(db=new_db)).output == ""

    def test_terminate(self, cluster: Cluster):
        result = cluster.terminate(
            databases=["foobar"],
            pids=[151515, 25235423],
            roles=["foo", "bar"],
            exclude_roles=["bar"],
            exclude_databases=["bar"],
            exclude_pids=[23332, 23323],
        )
        assert len(result) == 0

    def test_create_role(self, cluster: Cluster, psql, role):
        psql(f"DROP ROLE {role}")
        limit = 20
        password = "bar"
        cluster.roles.new(
            name=role,
            connection_limit=limit,
            password=password,
            superuser=False,
            replication=False,
            login=False,
        ).create()
        assert psql(self.role_query.format(role=role)).output == f"{role}|f|f|f|{limit}"

    def test_alter_role(self, cluster: Cluster, psql, role: str):
        limit = 20
        role_obj = cluster.roles[role]
        role_obj.connection_limit = limit
        role_obj.superuser = False
        role_obj.login = False
        role_obj.replication = False
        role_obj.alter()
        assert psql(self.role_query.format(role=role)).output == f"{role}|f|f|f|{limit}"

    def test_drop_role(self, cluster: Cluster, psql, role):
        cluster.roles[role].drop()
        result = psql(self.role_query.format(role=role)).output
        assert result == ""

    def test_create_replication_slot(self, replication_slot, plugin, db, psql, cluster_db: Cluster):
        psql(f"SELECT pg_drop_replication_slot('{replication_slot}')", db=db)
        cluster_db.replication_slots.new(name=replication_slot, plugin=plugin).create()
        result = psql(self.replication_slot_query.format(slot=replication_slot)).output
        assert result == f"{replication_slot}|{plugin}"

    def test_drop_replication_slot(self, replication_slot, psql, cluster_db: Cluster):
        cluster_db.replication_slots[replication_slot].drop()
        result = psql(self.replication_slot_query.format(slot=replication_slot)).output
        assert result == ""

    def test_roles(self, cluster: Cluster, role):
        assert isinstance(cluster.roles, objects.RoleCollection)
        assert role in cluster.roles

    def test_databases(self, cluster: Cluster, db):
        assert isinstance(cluster.databases, objects.DatabaseCollection)
        assert db in cluster.databases

    def test_reassign_owner(self, role, db, psql, cluster_db: Cluster, db_table_owner):
        cluster_db.reassign_owner(owner=role, new_owner="postgres")
        assert psql(self.dat_owner_query.format(db=db)).output == "postgres"
        results = psql(self.table_owner_query.format(name="tmpzzz", schema="public"), db=db).output
        assert results == "postgres"

    def test_reassign_owner_objects(self, db, psql, cluster_db: Cluster, db_table_owner):
        cluster_db.reassign_owner(
            objects=[cluster_db.databases[db], cluster_db.tables["tmpzzz"]],
            new_owner="postgres",
        )
        assert psql(self.dat_owner_query.format(db=db)).output == "postgres"
        results = psql(self.table_owner_query.format(name="tmpzzz", schema="public"), db=db).output
        assert results == "postgres"

    def test_doctest(self, doctest_globs_factory):
        from pgmob import cluster as cluster_module

        results = doctest.testmod(m=cluster_module, globs=doctest_globs_factory(cluster_module))
        assert results.failed == 0
