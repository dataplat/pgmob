from unittest.mock import call

import pytest

from pgmob import objects
from pgmob.objects.procedures import _BaseProcedure
from pgmob.sql import SQL, Identifier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _procedure_tuples_to_dicts(procedure_tuples):
    """Convert procedure namedtuples to provider-style dicts."""
    return [
        {
            "oid": p.oid,
            "name": p.name,
            "schema": p.schema,
            "owner": p.owner,
            "language": p.language,
            "kind": p.kind,
            "security_definer": p.security_definer,
            "leak_proof": p.leak_proof,
            "strict": p.strict,
            "volatility": p.volatility,
            "parallel_mode": p.parallel_mode,
            "argument_types": p.argument_types,
        }
        for p in procedure_tuples
    ]


def _get_key(proc):
    return proc.name if proc.schema == "public" else f"{proc.schema}.{proc.name}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider(mocker, procedure_tuples):
    """Mock metadata provider that returns procedure_tuples data."""
    provider = mocker.Mock()
    provider.get_procedures.return_value = _procedure_tuples_to_dicts(procedure_tuples)
    return provider


@pytest.fixture
def cluster_with_mock_provider(cluster, mock_provider):
    """Cluster with metadata_provider replaced by a mock."""
    cluster.metadata_provider = mock_provider
    return cluster


@pytest.fixture
def procedure_cursor(cursor, procedure_tuples):
    """Cursor that returns procedure tuples"""
    cursor.fetchall.return_value = procedure_tuples
    return cursor


@pytest.fixture
def procedure_collection(cluster_with_mock_provider):
    """Returns an initialized ProcedureCollection object using the mock provider."""
    collection = objects.ProcedureCollection(cluster=cluster_with_mock_provider)
    return collection


@pytest.fixture
def procedure(cluster, procedure_tuples):
    """Returns an initialized Procedure object"""
    data = procedure_tuples[0]
    return objects.Procedure(
        cluster=cluster,
        name=data.name,
        owner=data.owner,
        schema=data.schema,
        language=data.language,
        security_definer=data.security_definer,
        leak_proof=data.leak_proof,
        strict=data.strict,
        volatility=objects.Volatility(data.volatility),
        parallel_mode=objects.ParallelSafety(data.parallel_mode),
        argument_types=data.argument_types,
        oid=data.oid,
    )


class TestProcedure:
    def test_init(self, procedure, procedure_tuples):
        proc = procedure_tuples[0]

        assert procedure.name == proc.name
        assert procedure.schema == proc.schema
        assert str(procedure) == f"Procedure('{_get_key(proc)}')"
        assert procedure.kind in ["FUNCTION", "PROCEDURE"]
        assert procedure.security_definer == proc.security_definer
        assert procedure.leak_proof == proc.leak_proof
        assert procedure.strict == proc.strict
        assert isinstance(procedure.volatility, objects.Volatility)
        assert isinstance(procedure.parallel_mode, objects.ParallelSafety)

    def test_drop(self, procedure, cursor, pgmob_tester):
        procedure.drop()
        pgmob_tester.assertSql(f"DROP {procedure.kind} ", cursor)

    def test_alter(self, procedure, procedure_tuples, procedure_cursor):
        procedure_src = procedure_tuples[0]
        procedure_cursor.fetchall.return_value = [procedure_src]

        fqn = (
            SQL(".").join([Identifier(procedure.schema), Identifier(procedure.name)])
            + SQL(" (")
            + Identifier(procedure_src.argument_types[0])
            + SQL(")")
        )
        procedure.name = "bar"
        procedure.owner = "foo"
        procedure.schema = "zzz"
        procedure.alter()
        procedure_cursor.execute.assert_has_calls(
            [
                call(
                    SQL("ALTER PROCEDURE {procedure} OWNER TO {owner}").format(
                        procedure=fqn,
                        owner=Identifier("foo"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER PROCEDURE {procedure} SET SCHEMA {schema}").format(
                        procedure=fqn,
                        schema=Identifier("zzz"),
                    ),
                    None,
                ),
                call(
                    SQL("ALTER PROCEDURE {procedure} RENAME TO {new}").format(
                        procedure=fqn, new=Identifier("bar")
                    ),
                    None,
                ),
            ]
        )


class TestProcedureCollection:
    def test_init(self, procedure_collection, procedure_tuples):
        assert isinstance(procedure_collection, objects.ProcedureCollection)
        for variations in procedure_collection:
            assert isinstance(variations, objects.ProcedureVariations)
            for result in variations:
                assert isinstance(result, _BaseProcedure)
        for proc in procedure_tuples:
            variations = procedure_collection[_get_key(proc)]
            for result in variations:
                assert result.name == proc.name
                assert result.schema == proc.schema
                assert result.kind in ["FUNCTION", "PROCEDURE"]
                assert result.security_definer == proc.security_definer
                assert result.leak_proof == proc.leak_proof
                assert result.strict == proc.strict
                assert isinstance(result.volatility, objects.Volatility)
                assert isinstance(result.parallel_mode, objects.ParallelSafety)
        # unique properties
        proc0 = procedure_tuples[0]
        assert procedure_collection[proc0.schema + "." + proc0.name][0].argument_types == ["int4"]
        proc1 = procedure_tuples[1]
        assert procedure_collection[proc1.schema + "." + proc1.name][1].argument_types == None
        proc2 = procedure_tuples[2]
        assert procedure_collection[proc2.name][0].argument_types == ["int4"]
        proc3 = procedure_tuples[3]
        assert procedure_collection[proc3.schema + "." + proc3.name][0].argument_types == [
            "smallint",
            "text",
        ]

    def test_refresh_populates_collection(self, procedure_collection, procedure_tuples):
        """refresh() populates collection with ProcedureVariations from provider data."""
        for variations in procedure_collection:
            assert isinstance(variations, objects.ProcedureVariations)

    def test_all_procedures_present(self, procedure_tuples, procedure_collection):
        """All procedures from provider are present in the collection."""
        for proc in procedure_tuples:
            key = _get_key(proc)
            assert key in procedure_collection

    def test_metadata_mapping(self, procedure_tuples, procedure_collection):
        """All metadata fields are correctly mapped to procedure objects."""
        for proc in procedure_tuples:
            key = _get_key(proc)
            variations = procedure_collection[key]
            # Find the matching variation by argument_types
            matching = [v for v in variations if v.argument_types == proc.argument_types]
            assert len(matching) >= 1
            result = matching[0]
            assert result.name == proc.name
            assert result.schema == proc.schema
            assert result.owner == proc.owner
            assert result.language == proc.language
            assert result.security_definer == proc.security_definer
            assert result.leak_proof == proc.leak_proof
            assert result.strict == proc.strict
            assert result.volatility == objects.Volatility(proc.volatility)
            assert result.parallel_mode == objects.ParallelSafety(proc.parallel_mode)

    def test_refresh_calls_provider(self, procedure_collection, mock_provider):
        """refresh() calls provider.get_procedures() each time."""
        call_count_before = mock_provider.get_procedures.call_count
        procedure_collection.refresh()
        assert mock_provider.get_procedures.call_count == call_count_before + 1

    def test_empty_results(self, cluster_with_mock_provider, mock_provider):
        """Empty provider results produce an empty collection."""
        mock_provider.get_procedures.return_value = []
        collection = objects.ProcedureCollection(cluster=cluster_with_mock_provider)
        assert len(collection) == 0

    def test_schema_filtering(self, cluster_with_mock_provider, mock_provider, procedure_tuples):
        """Schema filter is passed through to provider.get_procedures()."""
        schema = "public"
        filtered = [p for p in _procedure_tuples_to_dicts(procedure_tuples) if p["schema"] == schema]
        mock_provider.get_procedures.return_value = filtered
        collection = objects.ProcedureCollection(cluster=cluster_with_mock_provider, schema=schema)
        mock_provider.get_procedures.assert_called_with(schema)
        for variations in collection:
            for proc in variations:
                assert proc.schema == schema

    def test_provider_attribute_set(self, cluster_with_mock_provider, mock_provider):
        """ProcedureCollection stores the provider from cluster.metadata_provider."""
        collection = objects.ProcedureCollection(cluster=cluster_with_mock_provider)
        assert collection.provider is mock_provider

    def test_refresh_repopulates_collection(self, procedure_collection, procedure_tuples, mock_provider):
        """refresh() clears and repopulates the collection."""
        key = _get_key(procedure_tuples[0])
        procedure_collection[key][0].schema = "foo"
        procedure_collection.refresh()
        assert procedure_collection[key][0].schema == procedure_tuples[0].schema

    def test_refresh(self, procedure_collection, procedure_tuples, procedure_cursor):
        proc = procedure_tuples[0]
        key = _get_key(proc)
        procedure_cursor.fetchall.return_value = [proc]
        procedure_collection[key][0].schema = "foo"
        procedure_collection[key][0].refresh()
        assert procedure_collection[key][0].schema == proc.schema
