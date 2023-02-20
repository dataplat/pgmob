from unittest.mock import call
import pytest
from pgmob.sql import SQL, Identifier
from pgmob import objects


@pytest.fixture
def sequence_cursor(cursor, sequence_tuples):
    """Cursor that returns sequence tuples"""
    cursor.fetchall.return_value = sequence_tuples
    return cursor


@pytest.fixture
def sequence_collection(cluster, sequence_cursor):
    """Returns an initialized SequenceCollection object"""
    collection = objects.SequenceCollection(cluster=cluster)
    return collection


@pytest.fixture
def sequence(cluster, sequence_tuples):
    """Returns an initialized Sequence object"""
    data = sequence_tuples[0]
    return objects.Sequence(
        cluster=cluster,
        name=data.sequencename,
        owner=data.sequenceowner,
        schema=data.schemaname,
        oid=data.oid,
    )


def _get_key(seq):
    return seq.sequencename if seq.schemaname == "public" else f"{seq.schemaname}.{seq.sequencename}"


class TestSequence:
    def test_init(self, sequence, sequence_tuples):
        seq = sequence_tuples[0]
        key = _get_key(seq)
        assert sequence.name == seq.sequencename
        assert sequence.owner == seq.sequenceowner
        assert sequence.schema == seq.schemaname
        assert sequence.data_type == None
        assert sequence.start_value == None
        assert sequence.min_value == None
        assert sequence.max_value == None
        assert sequence.increment_by == None
        assert sequence.cycle == None
        assert sequence.cache_size == None
        assert sequence.last_value == None
        assert sequence.oid == seq.oid
        assert str(sequence) == f"Sequence('{key}')"

    def test_drop(self, cursor, sequence, pgmob_tester):
        sequence.drop()
        pgmob_tester.assertSql(f"DROP SEQUENCE ", cursor)
        pgmob_tester.assertSql(sequence.name, cursor)
        pgmob_tester.assertSql(sequence.schema, cursor)

    def test_drop_cascade(self, cursor, sequence, pgmob_tester):
        sequence.drop(True)
        pgmob_tester.assertSql(f"DROP SEQUENCE ", cursor)
        pgmob_tester.assertSql(f" CASCADE", cursor)
        pgmob_tester.assertSql(sequence.name, cursor)
        pgmob_tester.assertSql(sequence.schema, cursor)

    def test_nextval(self, cursor, sequence):
        cursor.fetchall.return_value = [(1,)]
        assert sequence.nextval() == 1
        cursor.execute.assert_called_with(SQL("SELECT nextval(%s)"), (sequence.oid,))

    def test_currval(self, cursor, sequence):
        cursor.fetchall.return_value = [(1,)]
        assert sequence.currval() == 1
        cursor.execute.assert_called_with(SQL("SELECT currval(%s)"), (sequence.oid,))

    def test_setval(self, cursor, sequence):
        cursor.fetchall.return_value = [(1,)]
        sequence.setval(10)
        cursor.execute.assert_called_with(SQL("SELECT setval(%s, %s)"), (sequence.oid, 10))

    def test_refresh(self, sequence, sequence_cursor, sequence_tuples, pgmob_tester):
        seq = sequence_tuples[0]
        sequence.schema = "foo"
        sequence.refresh()
        assert sequence.name == seq[0]
        assert sequence.owner == seq[1]
        assert sequence.schema == seq[2]
        assert sequence.data_type == seq[3]
        assert sequence.start_value == seq[4]
        assert sequence.min_value == seq[5]
        assert sequence.max_value == seq[6]
        assert sequence.increment_by == seq[7]
        assert sequence.cycle == seq[8]
        assert sequence.cache_size == seq[9]
        assert sequence.last_value == seq[10]
        assert sequence.oid == seq[11]
        assert str(sequence) == f"Sequence('{_get_key(seq)}')"
        pgmob_tester.assertSql("FROM pg_catalog.pg_sequences", sequence_cursor)

    def test_alter(self, sequence_cursor, sequence, sequence_tuples):
        src = sequence_tuples[0]
        sequence_cursor.fetchall.return_value = [src]
        fqn = SQL(".").join([Identifier(sequence.schema), Identifier(sequence.name)])
        sequence.name = "bar"
        sequence.owner = "foo"
        sequence.schema = "zzz"
        sequence.alter()
        sequence_cursor.execute.assert_has_calls(
            [
                call(
                    SQL("ALTER SEQUENCE {sequence} OWNER TO {owner}").format(
                        sequence=fqn,
                        owner=Identifier("foo"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER SEQUENCE {sequence} SET SCHEMA {schema}").format(
                        sequence=fqn,
                        schema=Identifier("zzz"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER SEQUENCE {sequence} RENAME TO {new}").format(
                        sequence=fqn, new=Identifier("bar")
                    ),
                    None,
                ),
            ]
        )


class TestSequenceCollection:
    def test_init(self, sequence_collection, sequence_tuples):
        for result in sequence_collection:
            assert isinstance(result, objects.Sequence)
        for seq in sequence_tuples:
            key = _get_key(seq)
            result = sequence_collection[key]
            assert result.name == seq[0]
            assert result.owner == seq[1]
            assert result.schema == seq[2]
            assert result.data_type == seq[3]
            assert result.start_value == seq[4]
            assert result.min_value == seq[5]
            assert result.max_value == seq[6]
            assert result.increment_by == seq[7]
            assert result.cycle == seq[8]
            assert result.cache_size == seq[9]
            assert result.last_value == seq[10]
            assert result.oid == seq[11]
            assert str(result) == f"Sequence('{key}')"

    def test_refresh(self, sequence_collection: objects.SequenceCollection, sequence_tuples):
        key = _get_key(sequence_tuples[0])
        sequence_collection[key].name = "foo"
        sequence_collection.refresh()
        assert sequence_collection[key].name == sequence_tuples[0].sequencename
        assert len(sequence_collection[key]._changes) == 0
