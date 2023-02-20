from unittest.mock import call
import pytest
from pgmob.sql import SQL, Identifier
from pgmob import objects
from pgmob.objects.procedures import _BaseProcedure
from pgmob.util import Version


@pytest.fixture
def procedure_cursor(cursor, procedure_tuples):
    """Cursor that returns procedure tuples"""
    cursor.fetchall.return_value = procedure_tuples
    return cursor


@pytest.fixture
def procedure_collection(cluster, procedure_cursor):
    """Returns an initialized ProcedureCollection object"""
    cluster.version = Version("12.0")
    collection = objects.ProcedureCollection(cluster=cluster)
    return collection


@pytest.fixture
def procedure(cluster, procedure_tuples):
    """Returns an initialized Procedure object"""
    data = procedure_tuples[0]
    return objects.Procedure(
        cluster=cluster,
        name=data.proname,
        owner=data.proowner,
        schema=data.schemaname,
        language=data.prolang,
        security_definer=data.prosecdef,
        leak_proof=data.proleakproof,
        strict=data.proisstrict,
        volatility=objects.Volatility(data.provolatile),
        parallel_mode=objects.ParallelSafety(data.proparallel),
        argument_types=data.proargtypes,
        oid=data.oid,
    )


def _get_key(proc):
    return proc.proname if proc.schemaname == "public" else f"{proc.schemaname}.{proc.proname}"


class TestProcedure:
    def test_init(self, procedure, procedure_tuples):
        proc = procedure_tuples[0]

        assert procedure.name == proc.proname
        assert procedure.schema == proc.schemaname
        assert str(procedure) == f"Procedure('{_get_key(proc)}')"
        assert procedure.kind in ["FUNCTION", "PROCEDURE"]
        assert procedure.security_definer == proc.prosecdef
        assert procedure.leak_proof == proc.proleakproof
        assert procedure.strict == proc.proisstrict
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
            + Identifier(procedure_src.proargtypes[0])
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
                assert result.name == proc.proname
                assert result.schema == proc.schemaname
                assert result.kind in ["FUNCTION", "PROCEDURE"]
                assert result.security_definer == proc.prosecdef
                assert result.leak_proof == proc.proleakproof
                assert result.strict == proc.proisstrict
                assert isinstance(result.volatility, objects.Volatility)
                assert isinstance(result.parallel_mode, objects.ParallelSafety)
        # unique properties
        proc0 = procedure_tuples[0]
        assert procedure_collection[proc0.schemaname + "." + proc0.proname][0].argument_types == ["int4"]
        proc1 = procedure_tuples[1]
        assert procedure_collection[proc1.schemaname + "." + proc1.proname][1].argument_types == None
        proc2 = procedure_tuples[2]
        assert procedure_collection[proc2.proname][0].argument_types == ["int4"]
        proc3 = procedure_tuples[3]
        assert procedure_collection[proc3.schemaname + "." + proc3.proname][0].argument_types == [
            "smallint",
            "text",
        ]

    def test_refresh(self, procedure_collection, procedure_tuples, procedure_cursor):
        proc = procedure_tuples[0]
        key = _get_key(proc)
        procedure_cursor.fetchall.return_value = [proc]
        procedure_collection[key][0].schema = "foo"
        procedure_collection[key][0].refresh()
        assert procedure_collection[key][0].schema == proc.schemaname
