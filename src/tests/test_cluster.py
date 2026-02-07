from unittest.mock import MagicMock, call

import pytest
from pytest_mock import MockerFixture

from pgmob import objects, util
from pgmob.cluster import Cluster
from pgmob.errors import PostgresShellCommandError
from pgmob.objects import generic
from pgmob.sql import SQL, Identifier


class TestCluster:
    def _get_collection(self, mocker: MockerFixture, names: list, owner="postgres", schema="public"):
        col = generic.MappedCollection[generic._DynamicObject]()
        for name in names:
            obj = mocker.Mock()
            change = mocker.Mock()
            obj.name = name
            obj.owner = owner
            obj.schema = schema
            change.sql = SQL("foobar")
            change.params = None
            obj._changes = [change]
            col[name] = obj
        return col

    def test_init(self, cluster: Cluster, db_name: str, cursor: MagicMock, psycopg2_connection):
        cursor.execute.assert_called()
        assert cluster.adapter.connection == psycopg2_connection
        assert cluster.current_database == db_name
        assert cluster.version == util.Version("10.12")
        assert cluster.become is None

    def test_init_become(
        self,
        psycopg2_connection,
        db_name: str,
        cursor: MagicMock,
        cursor_fetch_version,
        mocker: MockerFixture,
    ):

        mocker.patch("pgmob.adapters.psycopg2.Psycopg2Cursor._convert_query", lambda _, x: x)
        cluster = Cluster(connection=psycopg2_connection, become="postgres")
        cursor.execute.assert_any_call(SQL("SET ROLE {role}").format(role=Identifier("postgres")), None)
        assert cluster.adapter.connection == psycopg2_connection
        assert cluster.current_database == db_name
        assert cluster.version == util.Version("10.12")
        assert cluster.become == "postgres"

    def test_execute(self, cluster: Cluster, cursor):
        query = "SELECT foo FROM bar WHERE FOO = %s"
        param = 5
        cluster.execute(query)
        cursor.execute.assert_called_with(query, None)

        cluster.execute(SQL(query), param)
        cursor.execute.assert_called_with(SQL(query), (param,))

        cluster.execute(SQL(query), (param,))
        cursor.execute.assert_called_with(SQL(query), (param,))

    def test_execute_cursor(self, cluster: Cluster, cursor):
        query = "SELECT foo FROM bar WHERE FOO = %s"
        param = 5

        cluster.execute_with_cursor(lambda x: x.execute(query))
        cursor.execute.assert_called_with(query, None)

        cluster.execute_with_cursor(lambda x: x.execute(query, (param,)))
        cursor.execute.assert_called_with(query, (param,))

    def test_run_os_command(
        self,
        psycopg2_connection,
        cursor,
        cursor_fetch_version,
    ):
        cluster = Cluster(connection=psycopg2_connection)
        cursor.fetchall.return_value = [(0,), ("foo",)]
        result = cluster.run_os_command("bar")
        assert cursor.execute.call_count == 5  # 1 by init, 4 by run_os_command
        assert result.text == "foo"
        assert result.exit_code == 0

    def test_run_os_command_failed(
        self,
        psycopg2_connection,
        cursor,
        cursor_fetch_version,
    ):
        cluster = Cluster(connection=psycopg2_connection)
        cursor.fetchall.return_value = [(1,), ("bar",)]
        with pytest.raises(PostgresShellCommandError):
            cluster.run_os_command("bar")

        result = cluster.run_os_command("bar", raise_exception=False)
        assert result.text == "bar"
        assert result.exit_code == 1

    def test_rename_database(
        self, cluster: Cluster, cursor, old_db_name: str, new_db_name: str, pgmob_tester, db_tuples
    ):
        cursor.fetchall.return_value = db_tuples
        db = cluster.databases[old_db_name]
        db.name = new_db_name
        db.alter()
        pgmob_tester.assertSql("ALTER DATABASE", cursor)
        pgmob_tester.assertSql("RENAME TO", cursor)

    def test_create_database(self, cluster: Cluster, cursor, db_name: str, pgmob_tester, db_tuples):
        template = "bar"
        owner = "foobar"
        cursor.fetchall.return_value = db_tuples
        cluster.databases.new(name=db_name, template=template, owner=owner, is_template=True).create()
        pgmob_tester.assertSql("CREATE DATABASE", cursor)

    def test_terminate(self, cluster: Cluster, cursor, pgmob_tester):
        databases = ["qwe", "rty"]
        exclude_databases = ["fba"]
        pids = [1234]
        exclude_pids = [123]
        roles = ["asdf", "werw"]
        exclude_roles = ["foo", "bar"]
        cursor.fetchall.return_value = [(1234, True)]
        assert cluster.terminate(
            databases=databases,
            exclude_databases=exclude_databases,
            roles=roles,
            exclude_roles=exclude_roles,
            pids=pids,
            exclude_pids=exclude_pids,
        ) == [1234]
        pgmob_tester.assertSql("SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity WHERE", cursor)

    def test_drop_database(self, cluster: Cluster, cursor, db_tuples, pgmob_tester):
        database = db_tuples[0].datname
        cursor.fetchall.side_effect = (db_tuples, [(True,)])
        cluster.databases[database].drop()
        pgmob_tester.assertSql("DROP DATABASE", cursor)

    def test_create_role(self, cluster: Cluster, cursor, role_tuples, pgmob_tester):
        role = "foo"
        limit = 20
        password = "bar"
        cursor.fetchall.return_value = role_tuples
        cluster.roles.new(
            name=role,
            connection_limit=limit,
            password=password,
            superuser=True,
            replication=False,
            login=False,
        ).create()
        pgmob_tester.assertSql("CREATE ROLE", cursor)
        pgmob_tester.assertSql("CONNECTION LIMIT", cursor)
        pgmob_tester.assertSql(str(limit), cursor)
        pgmob_tester.assertSql("SUPERUSER", cursor)
        pgmob_tester.assertSql("NOREPLICATION", cursor)
        pgmob_tester.assertSql("NOLOGIN", cursor)

    def test_drop_role(self, cluster: Cluster, cursor, role_tuples, pgmob_tester):
        role = role_tuples[0].rolname
        cursor.fetchall.return_value = role_tuples
        cluster.roles[role].drop()
        pgmob_tester.assertSql("DROP ROLE", cursor)

    def test_reload(self, cluster: Cluster, cursor):
        cursor.fetchall.return_value = [(True,)]
        cluster.reload()
        cursor.execute.assert_called_with(SQL("SELECT pg_reload_conf()"), None)

    def test_drop_replication_slot(
        self,
        cluster: Cluster,
        cursor,
        cursor_fetch_replication_slots,
        monkeypatch: pytest.MonkeyPatch,
        mocker: MockerFixture,
    ):
        slot = cursor_fetch_replication_slots[0].slot_name
        assert slot in cluster.replication_slots
        # mock call to terminate
        monkeypatch.setattr(cluster, "terminate", mocker.MagicMock())
        cluster.replication_slots[slot].drop()
        calls = [
            call(
                SQL(
                    "SELECT pg_terminate_backend(active_pid) FROM pg_catalog.pg_replication_slots WHERE slot_name = %s"
                ),
                (slot,),
            ),
            call(SQL("SELECT pg_drop_replication_slot(%s)"), (slot,)),
        ]
        cursor.execute.assert_has_calls(calls)

    def test_create_replication_slot(self, cluster: Cluster, cursor, slot_tuples, pgmob_tester):
        slot = "foo"
        plugin = "bar"
        cursor.fetchall.return_value = slot_tuples
        cluster.replication_slots.new(name=slot, plugin=plugin).create()
        pgmob_tester.assertSql("SELECT pg_create_logical_replication_slot", cursor)

    def test_roles(self, cluster: Cluster, cursor_fetch_roles):
        results = cluster.roles
        assert isinstance(results, objects.RoleCollection)
        for result in results:
            assert isinstance(result, objects.Role)
        for role in cursor_fetch_roles:
            result = results[role[0]]
            assert result.name == role[0]

    def test_databases(self, cluster: Cluster, cursor_fetch_databases):
        results = cluster.databases
        assert isinstance(results, objects.DatabaseCollection)
        for result in results:
            assert isinstance(result, objects.Database)
        for db in cursor_fetch_databases:
            result = results[db[0]]
            assert result.name == db[0]

    def test_sequences(self, cluster: Cluster, cursor_fetch_sequences):
        results = cluster.sequences
        assert isinstance(results, objects.SequenceCollection)
        for result in results:
            assert isinstance(result, objects.Sequence)
        for seq in cursor_fetch_sequences:
            key = seq[0] if seq[2] == "public" else f"{seq[2]}.{seq[0]}"
            result = results[key]
            assert result.name == seq[0]

    def test_tables(self, cluster: Cluster, cursor_fetch_tables):
        results = cluster.tables
        assert isinstance(results, objects.TableCollection)
        for result in results:
            assert isinstance(result, objects.Table)
        for tbl in cursor_fetch_tables:
            key = tbl[0] if tbl[2] == "public" else f"{tbl[2]}.{tbl[0]}"
            result = results[key]
            assert result.name == tbl[0]

    def test_views(self, cluster: Cluster, cursor_fetch_views):
        results = cluster.views
        assert isinstance(results, objects.ViewCollection)
        for result in results:
            assert isinstance(result, objects.View)
        for v in cursor_fetch_views:
            key = v[0] if v[2] == "public" else f"{v[2]}.{v[0]}"
            result = results[key]
            assert result.name == v[0]

    def test_replication_slots(self, cluster: Cluster, cursor_fetch_replication_slots):
        slot = cursor_fetch_replication_slots[0]
        results = cluster.replication_slots
        assert isinstance(results, objects.ReplicationSlotCollection)
        for result in results:
            assert isinstance(result, objects.ReplicationSlot)
        assert results is not None
        result = results[slot[0]]
        assert result.name == slot[0]

    def test_schemas(self, cluster: Cluster, cursor_fetch_schemas):
        schema = cursor_fetch_schemas[0]
        results = cluster.schemas
        assert isinstance(results, objects.SchemaCollection)
        for result in results:
            assert isinstance(result, objects.Schema)
        assert results is not None
        result = results[schema[0]]
        assert result.name == schema[0]

    def test_procedures(self, cluster: Cluster, cursor_fetch_procedures):
        results = cluster.procedures
        assert isinstance(results, objects.ProcedureCollection)
        assert results is not None
        for variation in results:
            assert isinstance(variation, objects.ProcedureVariations)
            for procitem in variation:
                assert procitem.__class__ in [objects.Procedure, objects.Function]
        for proc in cursor_fetch_procedures:
            key = proc.proname if proc.schemaname == "public" else f"{proc.schemaname}.{proc.proname}"
            result = results[key][0]
            assert result.name == proc.proname

    def test_hba_rules(self, cluster: Cluster, cursor_fetch_hba):
        results = cluster.hba_rules
        for line in [x[0] for x in cursor_fetch_hba]:
            assert line in results

    def test_hba_rules_alter(self, cluster: Cluster, cursor, pgmob_tester):
        hba_file = "pg_hba"
        cursor.fetchall.return_value = [(hba_file,)]
        cluster.hba_rules.alter()
        pgmob_tester.assertSql("COPY (SELECT lines FROM pg_hba ORDER BY id) TO", cursor)

    def test_refresh(self, cluster, cursor, role_tuples, db_tuples):
        cursor.fetchall.return_value = role_tuples
        old_roles = cluster.roles
        cursor.fetchall.return_value = db_tuples
        old_dbs = cluster.databases
        cluster.refresh()
        cursor.fetchall.return_value = role_tuples
        assert old_roles is not cluster.roles
        cursor.fetchall.return_value = db_tuples
        assert old_dbs is not cluster.databases

    def test_reassign_owner_objects(self, mocker: MockerFixture, cluster, cursor, cursor_fetch_roles):
        obj_collection = self._get_collection(mocker, ["foo", "bar"])
        cluster.reassign_owner(new_owner=cursor_fetch_roles[0].rolname, objects=obj_collection)
        cursor.execute.assert_called_with(
            SQL(";\n").join([SQL("foobar")] * 2),
            None,
        )

    def test_reassign_owner_reassign(self, mocker: MockerFixture, cluster, cursor, cursor_fetch_roles):
        cluster.reassign_owner(new_owner=cursor_fetch_roles[1].rolname, owner=cursor_fetch_roles[0].rolname)
        cursor.execute.assert_called_with(
            SQL("REASSIGN OWNED BY {old} TO {new}").format(
                old=Identifier(cursor_fetch_roles[0].rolname), new=Identifier(cursor_fetch_roles[1].rolname)
            ),
            None,
        )
