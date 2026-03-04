from unittest.mock import call

import pytest

from pgmob import objects
from pgmob.sql import SQL, Identifier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sequence_tuples_to_dicts(sequence_tuples):
    """Convert sequence namedtuples to provider-style dicts."""
    return [
        {
            "name": s.name,
            "owner": s.owner,
            "schema": s.schema,
            "data_type": s.data_type,
            "start_value": s.start_value,
            "min_value": s.min_value,
            "max_value": s.max_value,
            "increment_by": s.increment_by,
            "cycle": s.cycle,
            "cache_size": s.cache_size,
            "last_value": s.last_value,
            "oid": s.oid,
        }
        for s in sequence_tuples
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider(mocker, sequence_tuples):
    """Mock metadata provider that returns sequence_tuples data."""
    provider = mocker.Mock()
    provider.get_sequences.return_value = _sequence_tuples_to_dicts(sequence_tuples)
    return provider


@pytest.fixture
def cluster_with_mock_provider(cluster, mock_provider):
    """Cluster with metadata_provider replaced by a mock."""
    cluster.metadata_provider = mock_provider
    return cluster


@pytest.fixture
def sequence_cursor(cursor, sequence_tuples):
    """Cursor that returns sequence tuples"""
    cursor.fetchall.return_value = sequence_tuples
    return cursor


@pytest.fixture
def sequence_collection(cluster_with_mock_provider):
    """Returns an initialized SequenceCollection object using the mock provider."""
    collection = objects.SequenceCollection(cluster=cluster_with_mock_provider)
    return collection


@pytest.fixture
def sequence(cluster, sequence_tuples):
    """Returns an initialized Sequence object"""
    data = sequence_tuples[0]
    return objects.Sequence(
        cluster=cluster,
        name=data.name,
        owner=data.owner,
        schema=data.schema,
        oid=data.oid,
    )


def _get_key(seq):
    return seq.name if seq.schema == "public" else f"{seq.schema}.{seq.name}"


# ---------------------------------------------------------------------------
# TestSequence
# ---------------------------------------------------------------------------


class TestSequence:
    def test_init(self, sequence, sequence_tuples):
        seq = sequence_tuples[0]
        key = _get_key(seq)
        assert sequence.name == seq.name
        assert sequence.owner == seq.owner
        assert sequence.schema == seq.schema
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
        pgmob_tester.assertSql("DROP SEQUENCE ", cursor)
        pgmob_tester.assertSql(sequence.name, cursor)
        pgmob_tester.assertSql(sequence.schema, cursor)

    def test_drop_cascade(self, cursor, sequence, pgmob_tester):
        sequence.drop(True)
        pgmob_tester.assertSql("DROP SEQUENCE ", cursor)
        pgmob_tester.assertSql(" CASCADE", cursor)
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
        assert sequence.name == seq.name
        assert sequence.owner == seq.owner
        assert sequence.schema == seq.schema
        assert sequence.data_type == seq.data_type
        assert sequence.start_value == seq.start_value
        assert sequence.min_value == seq.min_value
        assert sequence.max_value == seq.max_value
        assert sequence.increment_by == seq.increment_by
        assert sequence.cycle == seq.cycle
        assert sequence.cache_size == seq.cache_size
        assert sequence.last_value == seq.last_value
        assert sequence.oid == seq.oid
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
    def test_init_populates_collection(self, sequence_collection, sequence_tuples):
        """refresh() populates collection with Sequence objects from provider data."""
        for result in sequence_collection:
            assert isinstance(result, objects.Sequence)

    def test_init_all_sequences_present(self, sequence_tuples, sequence_collection):
        """All sequences from provider are present in the collection."""
        for seq in sequence_tuples:
            key = _get_key(seq)
            assert key in sequence_collection

    def test_collection_indexing(self, sequence_tuples, sequence_collection):
        """Collection uses schema.name for non-public schemas, name for public."""
        for seq in sequence_tuples:
            key = _get_key(seq)
            result = sequence_collection[key]
            assert result.name == seq.name
            assert result.schema == seq.schema

    def test_metadata_mapping(self, sequence_tuples, sequence_collection):
        """All metadata fields are correctly mapped to Sequence objects."""
        for seq in sequence_tuples:
            key = _get_key(seq)
            result = sequence_collection[key]
            assert result.name == seq.name
            assert result.owner == seq.owner
            assert result.schema == seq.schema
            assert result.data_type == seq.data_type
            assert result.start_value == seq.start_value
            assert result.min_value == seq.min_value
            assert result.max_value == seq.max_value
            assert result.increment_by == seq.increment_by
            assert result.cycle == seq.cycle
            assert result.cache_size == seq.cache_size
            assert result.last_value == seq.last_value
            assert result.oid == seq.oid
            assert str(result) == f"Sequence('{key}')"

    def test_refresh_repopulates_collection(self, sequence_collection, sequence_tuples, mock_provider):
        """refresh() clears and repopulates the collection."""
        key = _get_key(sequence_tuples[0])
        sequence_collection[key].name = "foo"
        sequence_collection.refresh()
        assert sequence_collection[key].name == sequence_tuples[0].name
        assert len(sequence_collection[key]._changes) == 0

    def test_refresh_calls_provider(self, sequence_collection, mock_provider):
        """refresh() calls provider.get_sequences() each time."""
        call_count_before = mock_provider.get_sequences.call_count
        sequence_collection.refresh()
        assert mock_provider.get_sequences.call_count == call_count_before + 1

    def test_empty_results(self, cluster_with_mock_provider, mock_provider):
        """Empty provider results produce an empty collection."""
        mock_provider.get_sequences.return_value = []
        collection = objects.SequenceCollection(cluster=cluster_with_mock_provider)
        assert len(collection) == 0

    def test_schema_filtering(self, cluster_with_mock_provider, mock_provider, sequence_tuples):
        """Schema filter is passed through to provider.get_sequences()."""
        schema = "public"
        filtered = [s for s in _sequence_tuples_to_dicts(sequence_tuples) if s["schema"] == schema]
        mock_provider.get_sequences.return_value = filtered
        collection = objects.SequenceCollection(cluster=cluster_with_mock_provider, schema=schema)
        mock_provider.get_sequences.assert_called_with(schema)
        for result in collection:
            assert result.schema == schema

    def test_provider_attribute_set(self, cluster_with_mock_provider, mock_provider):
        """SequenceCollection stores the provider from cluster.metadata_provider."""
        collection = objects.SequenceCollection(cluster=cluster_with_mock_provider)
        assert collection.provider is mock_provider
