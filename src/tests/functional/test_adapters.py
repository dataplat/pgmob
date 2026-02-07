import pytest

from pgmob.adapters import ProgrammingError, detect_adapter
from pgmob.adapters.base import BaseAdapter, BaseCursor, BaseLargeObject
from pgmob.sql import SQL, Identifier, Literal

ADAPTERS = ["psycopg2"]


@pytest.fixture()
def adapter_factory(container, hostname, pg_password, db):
    """Adapter factory.

    Args:
        adapter_type (str): adapter type as defined by the adapter_params fixture.
    """

    def wrapper(adapter_type: str):
        if adapter_type == "psycopg2":
            from pgmob.adapters import psycopg2 as _psycopg2

            adapter = _psycopg2.Psycopg2Adapter()
            adapter.connect(
                host=hostname,
                port=5432,
                user="postgres",
                password=pg_password,
                dbname=db,
            )
            return adapter
        else:
            raise ValueError("Unknown type %s", adapter_type)

    return wrapper


@pytest.fixture(params=ADAPTERS)
def adapter(adapter_factory, request):
    """Parameterized adapter fixture. Would run all the test in the current scope with
    all possible permutations.
    """
    return adapter_factory(request.param)


@pytest.fixture()
def cursor(adapter):
    """Cursor object"""
    with adapter.cursor() as cur:
        yield cur


@pytest.fixture()
def lobject_factory(adapter: BaseAdapter, lo_ids_factory, db) -> BaseLargeObject:
    """Lobject object rw"""
    lo_ids = lo_ids_factory(db=db)

    def wrapper(mode="rw"):
        return adapter.lobject(lo_ids[0], mode)

    return wrapper


@pytest.fixture()
def lobject_r(adapter: BaseAdapter, lo_ids_factory, db) -> BaseLargeObject:
    """Lobject object read"""
    lo_ids = lo_ids_factory(db=db)
    with adapter.lobject(lo_ids[0], "r") as lob:
        yield lob


class TestCursor:
    def test_properties(self, cursor: BaseCursor):
        assert cursor.closed == False
        cursor.execute(SQL("SELECT 1 UNION SELECT 2"))
        assert cursor.rowcount == 2
        assert cursor.statusmessage == "SELECT 2"

    def test_close(self, cursor):
        assert cursor.closed == False
        cursor.close()
        assert cursor.closed == True

    def test_scalar(self, cursor: BaseCursor):
        assert cursor.scalar(SQL("SELECT 1")) == 1
        assert cursor.scalar(SQL("SELECT {val}").format(val=Literal(1))) == 1
        cursor.execute("CREATE TABLE a(b int); INSERT INTO a VALUES (1)")
        assert cursor.scalar(SQL("SELECT * from {table}").format(table=Identifier("a"))) == 1

    def test_execute(self, cursor: BaseCursor):
        cursor.execute(SQL("SELECT 1"))
        assert cursor.fetchone()[0] == 1
        cursor.execute(SQL("SELECT {val}").format(val=Literal(1)))
        assert cursor.fetchone()[0] == 1
        cursor.execute("CREATE TABLE a(b int); INSERT INTO a VALUES (1)")
        cursor.execute(SQL("SELECT * from {table}").format(table=Identifier("a")))
        assert cursor.fetchone()[0] == 1

    def test_executemany(self, cursor: BaseCursor):
        cursor.execute("CREATE TABLE a(b int)")
        cursor.executemany(SQL("INSERT INTO a VALUES (%s)"), [(1,), (2,)])
        cursor.execute(SQL("SELECT * FROM a ORDER BY 1"))
        assert cursor.fetchone()[0] == 1
        assert cursor.fetchone()[0] == 2

    def test_mogrify(self, cursor: BaseCursor):
        assert (
            cursor.mogrify(SQL("INSERT INTO {table} VALUES (%s)").format(table=Identifier("tab1")))
            == b'INSERT INTO "tab1" VALUES (%s)'
        )

    def test_fetchall(self, cursor: BaseCursor):
        cursor.execute(SQL("SELECT 1 UNION SELECT 2"))
        result = cursor.fetchall()
        assert result[0][0] == 1
        assert result[1][0] == 2

    def test_fetchone(self, cursor: BaseCursor):
        cursor.execute(SQL("SELECT 1 UNION SELECT 2"))
        assert cursor.fetchone()[0] == 1
        assert cursor.fetchone()[0] == 2


class TestLargeObject:
    @staticmethod
    def get_current(psql, db, lo_id):
        return psql(f"SELECT encode(data, 'escape') FROM pg_largeobject WHERE loid = {lo_id}", db=db).output

    def test_close(self, lobject_r: BaseLargeObject):
        assert lobject_r.closed == False
        lobject_r.close()
        assert lobject_r.closed == True

    def test_unlink(self, adapter, lo_ids_factory, psql, db):
        lo_id = lo_ids_factory(db=db)[0]
        with adapter.lobject(lo_id, "rw") as lobject_rw:
            lobject_rw.unlink()
            adapter.commit()
        assert self.get_current(psql, db, lo_id) == ""

        with pytest.raises(Exception), adapter.lobject(lo_id, "r") as lobject_r:
            with pytest.raises(Exception):
                lobject_r.unlink()

    def test_read(self, adapter, lo_ids_factory, db):
        lo_id = lo_ids_factory(db=db)[0]
        with adapter.lobject(lo_id, "r") as lobject_r:
            assert lobject_r.read() == "foobar\n"

        with adapter.lobject(lo_id, "b") as lobject_r:
            assert lobject_r.read() == bytes("foobar\n", encoding="UTF8")

    def test_write(self, adapter, lo_ids_factory, psql, db):
        lo_id = lo_ids_factory(db=db)[0]
        with adapter.lobject(lo_id, "rw") as lobject_rw:
            lobject_rw.write(b"new data")
            adapter.commit()
        assert self.get_current(psql, db, lo_id) == "new data"

        with pytest.raises(Exception), adapter.lobject(lo_id, "r") as lobject_r:
            with pytest.raises(Exception):
                lobject_r.write(b"new data2")

    def test_truncate(self, adapter, lo_ids_factory, psql, db):
        lo_id = lo_ids_factory(db=db)[0]
        with adapter.lobject(lo_id, "rw") as lobject_rw:
            lobject_rw.truncate(length=1)
            adapter.commit()
        assert self.get_current(psql, db, lo_id) == "f"

        with adapter.lobject(lo_id, "rw") as lobject_rw:
            lobject_rw.truncate()
            adapter.commit()
        assert self.get_current(psql, db, lo_id) == ""

        with pytest.raises(Exception), adapter.lobject(lo_id, "r") as lobject_r:
            with pytest.raises(Exception):
                lobject_r.truncate()


class TestAdapter:
    def test_connection(self, adapter: BaseAdapter):
        assert adapter.is_connected == True
        assert adapter.has_connection == True

        connection = adapter.get_connection()
        assert connection is not None

        assert adapter.has_connection == True
        adapter.connection = None
        assert adapter.has_connection == False
        assert adapter.is_connected == False

        adapter.set_connection(connection)
        assert adapter.has_connection == True
        assert adapter.is_connected == True

        adapter.close_connection()
        assert adapter.has_connection == True
        assert adapter.is_connected == False

    def test_transactions(self, adapter: BaseAdapter):
        assert adapter.is_in_transaction == False

        with adapter.cursor() as cur:
            cur.execute("BEGIN")
            assert adapter.is_in_transaction == True
        adapter.commit()
        assert adapter.is_in_transaction == False

        with adapter.cursor() as cur:
            cur.execute("BEGIN")
            assert adapter.is_in_transaction == True
        adapter.rollback()
        assert adapter.is_in_transaction == False

    def test_autocommit(self, adapter: BaseAdapter):
        assert adapter.get_autocommit() == False

        with adapter.cursor() as cur:
            cur.execute("CREATE TABLE a(b int)")
            assert adapter.is_in_transaction == True
            adapter.rollback()
            assert adapter.is_in_transaction == False
            with pytest.raises(ProgrammingError):
                cur.execute("DROP TABLE a")
            assert adapter.is_in_transaction == True
            adapter.commit()

        adapter.set_autocommit(True)
        with adapter.cursor() as cur:
            cur.execute("CREATE TABLE a(b int)")
            assert adapter.is_in_transaction == False
            cur.execute("DROP TABLE a")


def test_detect_adapter():
    assert isinstance(detect_adapter(), BaseAdapter)
