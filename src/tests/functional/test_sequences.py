import pytest
from pgmob import objects


@pytest.fixture
def sequences(psql, db, cluster_db):
    """Creates a set of sequences"""
    sequence_list = [
        "public.alterschema",
        "public.ownertest",
        "public.rename",
        "public.props",
    ]
    for s in sequence_list:
        psql(f"CREATE SEQUENCE {s}", db=db)
    psql("CREATE TABLE public.tmpzzz (a int GENERATED ALWAYS AS IDENTITY)", db=db)

    seqs = objects.SequenceCollection(cluster=cluster_db)
    yield seqs


class TestSequences:
    sequence_query = "SELECT {field} FROM pg_catalog.pg_sequences WHERE sequencename = '{name}' AND schemaname = '{schema}'"

    def test_init(self, sequences):
        assert isinstance(sequences, objects.SequenceCollection)
        seq = sequences["tmpzzz_a_seq"]
        assert seq.name == "tmpzzz_a_seq"
        assert seq.owner == "postgres"
        assert seq.schema == "public"
        assert seq.data_type == "integer"
        assert seq.start_value == 1
        assert seq.min_value == 1
        assert seq.max_value > 1
        assert seq.increment_by == 1
        assert seq.cycle == False
        assert seq.cache_size == 1
        assert seq.last_value is None
        assert seq.oid > 0

    def test_value_retrieve(self, sequences):
        seq = sequences["tmpzzz_a_seq"]
        assert seq.nextval() == 1
        assert seq.currval() == 1

    def test_value_set(self, sequences):
        seq = sequences["tmpzzz_a_seq"]
        seq.setval(10)
        assert seq.currval() == 10
        seq.setval(20, True)
        assert seq.currval() == 20

    # setters
    def test_owner(self, sequences, psql, role, db):
        seq = sequences["ownertest"]
        seq.owner = role
        assert seq.owner == role
        results = psql(
            self.sequence_query.format(field="sequenceowner", name="ownertest", schema="public"),
            db=db,
        ).output
        assert results == "postgres"
        seq.alter()
        results = psql(
            self.sequence_query.format(field="sequenceowner", name="ownertest", schema="public"),
            db=db,
        ).output
        assert results == role
        assert seq.owner == role
        assert psql("DROP SEQUENCE ownertest", db=db).exit_code == 0

    def test_data_type(self, sequences, psql, db):
        def get_current():
            return psql(
                self.sequence_query.format(field="data_type", name="props", schema="public"),
                db=db,
            ).output

        seq = sequences["props"]
        seq.data_type = "smallint"
        assert seq.data_type == "smallint"
        assert get_current() == "bigint"
        seq.alter()
        assert get_current() == "smallint"
        assert seq.data_type == "smallint"

    def test_values(self, sequences, psql, db):
        def get_current():
            return psql(
                self.sequence_query.format(
                    field="min_value, start_value, max_value, increment_by",
                    name="props",
                    schema="public",
                ),
                db=db,
            ).output

        seq = sequences["props"]
        seq.start_value = 101
        seq.min_value = -11
        seq.max_value = 202
        seq.increment_by = 2
        assert seq.start_value == 101
        assert seq.min_value == -11
        assert seq.max_value == 202
        assert seq.increment_by == 2
        assert get_current() == "1|1|9223372036854775807|1"
        seq.alter()
        assert get_current() == "-11|101|202|2"
        assert seq.start_value == 101
        assert seq.min_value == -11
        assert seq.max_value == 202
        assert seq.increment_by == 2

    def test_schema(self, sequences, psql, db, schema):
        def get_current(schema="public"):
            return psql(
                self.sequence_query.format(
                    field="schemaname",
                    name="alterschema",
                    schema=schema,
                ),
                db=db,
            ).output

        seq = sequences["alterschema"]
        seq.schema = "tmpdoittwice"
        seq.schema = schema
        assert seq.schema == schema
        assert get_current() == "public"
        seq.alter()
        sequences.refresh()
        seq = sequences["tmp.alterschema"]
        assert get_current(schema) == schema
        assert seq.schema == schema

    def test_name(self, sequences, psql, db):
        def get_current(name="rename"):
            return psql(
                self.sequence_query.format(
                    field="sequencename",
                    name=name,
                    schema="public",
                ),
                db=db,
            ).output

        seq = sequences["rename"]
        seq.name = "tmpdoittwice"
        seq.name = "renamed"
        assert seq.name == "renamed"
        assert get_current() == "rename"
        seq.alter()
        sequences.refresh()
        seq = sequences["renamed"]
        assert get_current("renamed") == "renamed"
        assert seq.name == "renamed"

    def test_drop(self, sequences, psql, db):
        sequences["props"].drop()
        result = psql(
            self.sequence_query.format(
                field="schemaname",
                name="props",
                schema="public",
            ),
            db=db,
        ).output
        assert result == ""
        # TODO: items should be dropped from collections as well
        # assert "props" not in sequences
