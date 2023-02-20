import pytest
from pgmob import objects


@pytest.fixture
def procedures(psql, db, cluster_db, schema):
    """Creates a set of procedures"""
    func_list = ["public.tmpzzz", f"{schema}.tmpzzz"]
    for f in func_list:
        assert (
            psql(f"CREATE FUNCTION {f} (a int) RETURNS int" " AS 'SELECT $1 a' LANGUAGE SQL", db=db).exit_code
            == 0
        )
        assert psql(f"CREATE FUNCTION {f} () RETURNS int AS 'SELECT 1' LANGUAGE SQL", db=db).exit_code == 0

    proc_list = ["public.tmpyyy", "public.tmprename"]
    for p in proc_list:
        assert psql(f"CREATE PROCEDURE {p} () AS 'SELECT 1' LANGUAGE SQL", db=db).exit_code == 0
    procs = objects.ProcedureCollection(cluster=cluster_db)
    yield procs


class TestProcedures:
    proc_query = (
        "SELECT {field} FROM pg_catalog.pg_proc p"
        " JOIN pg_catalog.pg_namespace s ON p.pronamespace = s.oid"
        " JOIN pg_catalog.pg_roles r on p.proowner = r.oid "
        " WHERE p.proname = '{name}' AND s.nspname = '{schema}' AND "
        "(SELECT array_agg(t.typname)"
        "FROM unnest(p.proargtypes) WITH ORDINALITY as args(oid)"
        "JOIN pg_type t ON args.oid = t.oid) {equals}"
    )

    def test_init(self, procedures, cluster):
        # FUNCTION
        procvariations = procedures["tmpzzz"]
        for proc in procvariations:
            assert proc.name == "tmpzzz"
            assert proc.owner == "postgres"
            assert proc.schema == "public"
            assert proc.oid > 0
            assert proc.kind == "FUNCTION"
            assert not proc.security_definer
            assert not proc.leak_proof
            assert not proc.strict
            assert proc.volatility == objects.Volatility.VOLATILE
            assert proc.parallel_mode == objects.ParallelSafety.UNSAFE
            assert proc.argument_types in [["int4"], None]

        procvariations = procedures["tmp.tmpzzz"]
        for proc in procvariations:
            assert proc.name == "tmpzzz"
            assert proc.owner == "postgres"
            assert proc.schema == "tmp"
            assert proc.oid > 0
            assert proc.argument_types in [["int4"], None]

        if cluster.version.major >= 11:
            # PROCEDURE
            proc = procedures["tmpyyy"][0]
            assert proc.name == "tmpyyy"
            assert proc.owner == "postgres"
            assert proc.schema == "public"
            assert proc.oid > 0
            assert proc.kind == "PROCEDURE"
            assert not proc.security_definer
            assert not proc.leak_proof
            assert not proc.strict
            assert proc.volatility == objects.Volatility.VOLATILE
            assert proc.parallel_mode == objects.ParallelSafety.UNSAFE
            assert proc.argument_types == None

    def test_owner(self, procedures, db, psql, role):
        def get_current():
            return psql(
                self.proc_query.format(
                    field="r.rolname", name="tmpzzz", schema="public", equals=" = ARRAY['int4']::name[]"
                ),
                db=db,
            ).output

        proc = [x for x in procedures["tmpzzz"] if x.argument_types == ["int4"]][0]
        proc.owner = role
        assert proc.owner == role
        assert get_current() == "postgres"
        proc.alter()
        assert get_current() == role
        assert proc.owner == role
        assert psql("DROP FUNCTION tmpzzz(int)", db=db).exit_code == 0

    def test_schema(self, procedures, db, psql, schema, cluster):
        def get_current(schema="public"):
            return psql(
                self.proc_query.format(field="s.nspname", name="tmpyyy", schema=schema, equals=" IS NULL"),
                db=db,
            ).output

        if cluster.version.major >= 11:
            proc = procedures["tmpyyy"][0]
            proc.schema = "tmpdoittwice"
            proc.schema = schema
            assert proc.schema == schema
            assert get_current() == "public"
            proc.alter()
            procedures.refresh()
            proc = procedures["tmp.tmpyyy"][0]
            assert get_current(schema) == schema
            assert proc.schema == schema
        else:
            pytest.skip(reason="Current Postgres version doesn't support procedures")

    def test_name(self, procedures, db, psql, cluster):
        def get_current(name):
            return psql(
                self.proc_query.format(field="p.proname", name=name, schema="public", equals=" IS NULL"),
                db=db,
            ).output

        if cluster.version.major >= 11:
            proc = procedures["tmprename"][0]
            proc.name = "tmpdoittwice"
            proc.name = "tmprenamed"
            assert proc.name == "tmprenamed"
            assert get_current("tmprename") == "tmprename"
            proc.alter()
            procedures.refresh()
            proc = procedures["tmprenamed"][0]
            assert get_current("tmprenamed") == "tmprenamed"
            assert proc.name == "tmprenamed"
        else:
            pytest.skip(reason="Current Postgres version doesn't support procedures")

    def test_drop(self, procedures, db, psql, cluster, schema):
        def get_current(name, schema="public", is_null=True):
            return psql(
                self.proc_query.format(
                    field="p.proname",
                    name=name,
                    schema=schema,
                    equals=" IS NULL" if is_null else " = ARRAY['int4']::name[]",
                ),
                db=db,
            ).output

        assert get_current("tmpyyy") == "tmpyyy"
        if cluster.version.major >= 11:
            procedures["tmpyyy"][0].drop()
            assert get_current("tmpyyy") == ""

        assert get_current("tmpzzz", schema=schema) == "tmpzzz"
        assert get_current("tmpzzz", schema=schema, is_null=False) == "tmpzzz"
        for p in procedures[f"{schema}.tmpzzz"]:
            p.drop(cascade=True)
        assert get_current("tmpzzz", schema=schema) == ""
        assert get_current("tmpzzz", schema=schema, is_null=False) == ""
        procedures.refresh()
        assert "tmpyyy" not in procedures
        assert "tmp.tmpzzz" not in procedures
