from collections import namedtuple
from typing import List
import pytest
from unittest.mock import Mock
from pytest_mock import MockerFixture
from pgmob.sql import Composed
from pgmob.adapters.base import BaseAdapter
from pgmob.cluster import Cluster


class PGMobTester:
    @staticmethod
    def _parse_calls(*args, statement: int = None) -> List[str]:
        singletons: List[str] = []
        statements = [args[statement]] if statement else args
        for singleton in [x.args[0] for x in statements]:
            if isinstance(singleton, Composed):
                singletons.extend([str(x._value) for x in singleton._parts])
            else:
                singletons.append(singleton._value)
        return singletons

    @staticmethod
    def assertSql(sql: str, cursor: Mock, statement: int = None, mogrify: bool = False):
        singletons = PGMobTester._parse_calls(
            *(cursor.mogrify.call_args_list if mogrify else cursor.execute.call_args_list)
        )
        assert any(
            [sql in x for x in singletons]
        ), "{sql} was supposed to be among statements:\n{stmts}".format(sql=sql, stmts="\n".join(singletons))


@pytest.fixture
def pgmob_tester():
    return PGMobTester()


@pytest.fixture
def cursor(mocker):
    """Cursor object"""
    cursor = mocker.MagicMock()
    return cursor


@pytest.fixture
def lobject(mocker):
    """Large Object handler"""
    lobject = mocker.MagicMock()
    return lobject


@pytest.fixture
def cursor_fetch_version(cursor, db_name: str):
    """Set cursor with a version response"""
    cursor.fetchall.return_value = [
        (
            db_name,
            (
                "PostgreSQL 10.12 on x86_64-pc-linux-gnu"
                ", compiled by gcc (GCC) 4.8.5 20150623 (Red Hat 4.8.5-39), 64-bit"
            ),
        )
    ]
    return cursor


@pytest.fixture
def psycopg2_connection(mocker: MockerFixture, cursor, lobject):
    """psycopg2 connection emulator"""
    pg_conn = mocker.MagicMock()
    pg_conn.cursor.return_value = cursor
    pg_conn.lobject.return_value = lobject
    pg_conn.closed = False
    return pg_conn


@pytest.fixture
def db_name():
    """Test database name"""
    return "pgmobdb"


@pytest.fixture
def old_db_name(db_name):
    """Test database name"""
    return db_name


@pytest.fixture
def new_db_name():
    """Test database name"""
    return "pgmobdbnew"


@pytest.fixture
def cluster(
    psycopg2_connection,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    cursor,
    cursor_fetch_version,
):
    """Returns a cluster object with mocked connection and run_os_command"""
    mocker.patch("pgmob.adapters.psycopg2.Psycopg2Cursor._convert_query", lambda _, x: x)
    cluster = Cluster(connection=psycopg2_connection)
    cursor.fetchall.return_value = None
    monkeypatch.setattr(cluster, "run_os_command", mocker.Mock())
    return cluster


@pytest.fixture
def slot_tuples():
    """A list of Replication slot tuples"""
    ReplicationSlotTuple = namedtuple(
        "ReplicationSlotTuple",
        [
            "slot_name",
            "plugin",
            "slot_type",
            "database",
            "temporary",
            "active",
            "active_pid",
            "xmin",
            "catalog_xmin",
            "restart_lsn",
            "confirmed_flush_lsn",
        ],
    )
    return [
        ReplicationSlotTuple(
            slot_name="slot1",
            plugin="some_plugin",
            slot_type="logical",
            database="mydatabase",
            temporary=False,
            active=True,
            active_pid=4564,
            xmin="AB2D/457D89CA5",
            catalog_xmin="AB2D/457D89CA2",
            restart_lsn="AB2D/457D89CA53",
            confirmed_flush_lsn="AB2D/457D89CA4",
        ),
    ]


@pytest.fixture
def cursor_fetch_replication_slots(cursor, slot_tuples):
    """Makes the cursor to return Replication Slot data.
    Returns the list of tuples describing the slot.
    """
    cursor.fetchall.return_value = slot_tuples
    return slot_tuples


@pytest.fixture
def role_tuples():
    """Returns a list of Role Tuples"""
    RoleTuple = namedtuple(
        "RoleTuple",
        [
            "rolname",
            "rolsuper",
            "rolinherit",
            "rolcreaterole",
            "rolcreatedb",
            "rolcanlogin",
            "rolreplication",
            "rolconnlimit",
            "rolvaliduntil",
            "rolbypassrls",
            "oid",
        ],
    )
    return [
        RoleTuple(
            rolname="pgmob1",
            rolsuper=True,
            rolinherit=True,
            rolcreaterole=True,
            rolcreatedb=True,
            rolcanlogin=True,
            rolreplication=True,
            rolconnlimit=-1,
            rolvaliduntil=None,
            rolbypassrls=True,
            oid=456789,
        ),
        RoleTuple(
            rolname="pgmob2",
            rolsuper=False,
            rolinherit=False,
            rolcreaterole=False,
            rolcreatedb=False,
            rolcanlogin=False,
            rolreplication=False,
            rolconnlimit=20,
            rolvaliduntil=None,
            rolbypassrls=False,
            oid=123456,
        ),
    ]


@pytest.fixture
def cursor_fetch_roles(cursor, role_tuples):
    """Makes the cursor to return Role data.
    Returns a list of tuples describing the roles.
    """
    cursor.fetchall.return_value = role_tuples
    return role_tuples


@pytest.fixture
def schema_tuples(role_tuples):
    """Returns a list of Schema tuples"""
    SchemaTuple = namedtuple(
        typename="SchemaTuple",
        field_names=[
            "nspname",
            "nspowner",
            "oid",
        ],
    )
    return [
        SchemaTuple("pgmob1", role_tuples[0].rolname, 76461),
        SchemaTuple("pgmob2", role_tuples[1].rolname, 76462),
    ]


@pytest.fixture
def view_tuples(role_tuples, schema_tuples):
    """Returns a list of View tuples"""

    ViewTuple = namedtuple(
        typename="ViewTuple",
        field_names=[
            "viewname",
            "viewowner",
            "schemaname",
            "oid",
        ],
    )
    return [
        ViewTuple(
            viewname="view1",
            viewowner=role_tuples[0].rolname,
            schemaname=schema_tuples[0].nspname,
            oid=13541,
        ),
        ViewTuple(
            viewname="view2",
            viewowner="postgres",
            schemaname="public",
            oid=64642,
        ),
        ViewTuple(
            viewname="view3",
            viewowner=role_tuples[1].rolname,
            schemaname=schema_tuples[1].nspname,
            oid=79146,
        ),
    ]


@pytest.fixture
def table_tuples(role_tuples, schema_tuples):
    """Returns a list of Table tuples"""
    TableTuple = namedtuple(
        typename="TableTuple",
        field_names=[
            "tablename",
            "tableowner",
            "schemaname",
            "tablespace",
            "rowsecurity",
            "oid",
        ],
    )
    return [
        TableTuple(
            tablename="tab1",
            tableowner=role_tuples[0].rolname,
            schemaname=schema_tuples[0].nspname,
            tablespace="pg_default",
            rowsecurity=False,
            oid=45678,
        ),
        TableTuple(
            tablename="tab2",
            tableowner=role_tuples[0].rolname,
            schemaname="public",
            tablespace="pg_default",
            rowsecurity=False,
            oid=87348,
        ),
        TableTuple(
            tablename="tab3",
            tableowner=role_tuples[1].rolname,
            schemaname=schema_tuples[1].nspname,
            tablespace="pgmobnsp",
            rowsecurity=True,
            oid=78664,
        ),
    ]


@pytest.fixture
def sequence_tuples(role_tuples, schema_tuples):
    """Returns a list of Sequence tuples"""
    SequenceTuple = namedtuple(
        typename="SequenceTuple",
        field_names=[
            "sequencename",
            "sequenceowner",
            "schemaname",
            "data_type",
            "start_value",
            "min_value",
            "max_value",
            "increment_by",
            "cycle",
            "cache_size",
            "last_value",
            "oid",
        ],
    )
    return [
        SequenceTuple(
            sequencename="seq1",
            sequenceowner=role_tuples[0].rolname,
            schemaname=schema_tuples[0].nspname,
            data_type="smallint",
            start_value=3,
            min_value=-1,
            max_value=100,
            increment_by=1,
            cycle=False,
            cache_size=1,
            last_value=1,
            oid=11235,
        ),
        SequenceTuple(
            sequencename="seq2",
            sequenceowner=role_tuples[0].rolname,
            schemaname="public",
            data_type="bigint",
            start_value=0,
            min_value=0,
            max_value=200,
            increment_by=2,
            cycle=True,
            cache_size=1,
            last_value=2,
            oid=53462,
        ),
        SequenceTuple(
            sequencename="seq3",
            sequenceowner=role_tuples[1].rolname,
            schemaname=schema_tuples[1].nspname,
            data_type="smallint",
            start_value=-1,
            min_value=3,
            max_value=-200,
            increment_by=-1,
            cycle=False,
            cache_size=1,
            last_value=1,
            oid=16461,
        ),
    ]


@pytest.fixture
def db_tuples(role_tuples, old_db_name, new_db_name):
    """Returns a list of Database tuples"""
    DatabaseTuple = namedtuple(
        typename="DatabaseTuple",
        field_names=[
            "datname",
            "datowner",
            "encoding",
            "datcollate",
            "datctype",
            "datistemplate",
            "datallowconn",
            "datconnlimit",
            "datlastsysoid",
            "datfrozenxid",
            "datminmxid",
            "tablespace",
            "datacl",
            "oid",
        ],
    )
    return [
        DatabaseTuple(
            datname=old_db_name,
            datowner=role_tuples[0].rolname,
            encoding="UTF8",
            datcollate="en_US.utf8",
            datctype="en_US.utf8",
            datistemplate=True,
            datallowconn=False,
            datconnlimit=-1,
            datlastsysoid=123,
            datfrozenxid="AB2D/457D89CA2",
            datminmxid="AB2D/457D89CA1",
            tablespace="pg_default",
            datacl="{=c/owner,owner=CTc/owner}".replace("owner", role_tuples[0].rolname),
            oid=3401,
        ),
        DatabaseTuple(
            datname=new_db_name,
            datowner=role_tuples[1].rolname,
            encoding="UTF8",
            datcollate="en_US.utf8",
            datctype="en_US.utf8",
            datistemplate=False,
            datallowconn=True,
            datconnlimit=20,
            datlastsysoid=345,
            datfrozenxid="AB2D/457D89CA3",
            datminmxid="AB2D/457D89CA0",
            tablespace="customtbsp",
            datacl="{=c/postgres,postgres=CTc/postgres}",
            oid=3402,
        ),
    ]


@pytest.fixture
def hba_tuples():
    """Returns a list of HBA Rules tuples"""
    return [
        ("#hba file",),
        ("",),
        ("# empty line above",),
        ("local all all trust",),
        ("host all all 127.0.0.1/32 trust",),
        ("#that's enough",),
    ]


@pytest.fixture
def large_object_tuples(role_tuples):
    """Returns a list of Large Object tuples"""
    LargeObjectTuple = namedtuple(
        typename="LargeObjectTuple",
        field_names=[
            "oid",
            "lomowner",
        ],
    )
    return [
        LargeObjectTuple(oid=102, lomowner=role_tuples[0].rolname),
        LargeObjectTuple(oid=2344, lomowner="postgres"),
        LargeObjectTuple(oid=37869, lomowner=role_tuples[1].rolname),
    ]


@pytest.fixture
def procedure_tuples(role_tuples, schema_tuples):
    """Returns a list of Procedure tuples"""
    ProcedureTuple = namedtuple(
        typename="ProcedureTuple",
        field_names=[
            "oid",
            "proname",
            "schemaname",
            "proowner",
            "prolang",
            "prokind",
            "prosecdef",
            "proleakproof",
            "proisstrict",
            "provolatile",
            "proparallel",
            "proargtypes",
        ],
    )
    return [
        ProcedureTuple(
            proname="function1",
            proowner=role_tuples[0].rolname,
            schemaname=schema_tuples[0].nspname,
            prolang="Fortran",
            prokind="f",
            prosecdef=False,
            proleakproof=False,
            proisstrict=False,
            provolatile="i",
            proparallel="s",
            proargtypes=["int4"],
            oid=53462,
        ),
        ProcedureTuple(
            proname="function1",
            proowner=role_tuples[0].rolname,
            schemaname=schema_tuples[0].nspname,
            prolang="Fortran",
            prokind="f",
            prosecdef=False,
            proleakproof=False,
            proisstrict=False,
            provolatile="s",
            proparallel="s",
            proargtypes=None,
            oid=53462,
        ),
        ProcedureTuple(
            proname="function2",
            proowner="postgres",
            schemaname="public",
            prolang="Pascal",
            prokind="f",
            prosecdef=False,
            proleakproof=False,
            proisstrict=False,
            provolatile="v",
            proparallel="r",
            proargtypes=["int4"],
            oid=53462,
        ),
        ProcedureTuple(
            proname="procedure1",
            proowner=role_tuples[1].rolname,
            schemaname=schema_tuples[1].nspname,
            prolang="Algol",
            prokind="p",
            prosecdef=True,
            proleakproof=True,
            proisstrict=True,
            provolatile="v",
            proparallel="u",
            proargtypes=["smallint", "text"],
            oid=53463,
        ),
    ]


@pytest.fixture
def cursor_fetch_databases(cursor, db_tuples):
    """Makes the cursor to return Database data.
    Returns a list of tuples describing databases.
    """
    cursor.fetchall.return_value = db_tuples
    return db_tuples


@pytest.fixture
def cursor_fetch_sequences(cursor, sequence_tuples):
    """Makes the cursor to return Sequence data.
    Returns a list of tuples describing sequences.
    """
    cursor.fetchall.return_value = sequence_tuples
    return sequence_tuples


@pytest.fixture
def cursor_fetch_tables(cursor, table_tuples):
    """Makes the cursor to return Table data.
    Returns a list of tuples describing tables.
    """
    cursor.fetchall.return_value = table_tuples
    return table_tuples


@pytest.fixture
def cursor_fetch_views(cursor, view_tuples):
    """Makes the cursor to return View data.
    Returns a list of tuples describing views.
    """
    cursor.fetchall.return_value = view_tuples
    return view_tuples


@pytest.fixture
def cursor_fetch_schemas(cursor, schema_tuples):
    """Makes the cursor to return Schema data.
    Returns a list of tuples describing schemas.
    """
    cursor.fetchall.return_value = schema_tuples
    return schema_tuples


@pytest.fixture
def cursor_fetch_procedures(cursor, procedure_tuples):
    """Makes the cursor to return Procedure data.
    Returns a list of tuples describing procedures.
    """
    cursor.fetchall.return_value = procedure_tuples
    return procedure_tuples


@pytest.fixture
def cursor_fetch_hba(cursor, hba_tuples):
    """Makes the cursor to return HBA data.
    Returns a list of tuples describing HBA Rules.
    """
    cursor.fetchall.return_value = hba_tuples
    return hba_tuples


@pytest.fixture
def mock_cluster(mocker: MockerFixture):
    """Mock cluster object"""
    mock = mocker.Mock(spec=Cluster)
    mock.adapter = mocker.Mock(spec=BaseAdapter)
    return mock
