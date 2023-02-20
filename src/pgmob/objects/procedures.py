"""Postgresql procedure objects"""
from typing import TYPE_CHECKING, Dict, List, Optional, Type
from ..sql import SQL, Identifier, Composable
from ..errors import *
from .. import util
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class ProcedureKind(generic.AliasEnum):
    """Postgres procedure kinds"""

    FUNCTION = "FUNCTION"
    PROCEDURE = "PROCEDURE"
    AGGREGATE = "AGGREGATE"
    WINDOW_FUNCTION = "WINDOW FUNCTION"


class Volatility(generic.AliasEnum):
    """Postgres function volatility, as described in
    https://www.postgresql.org/docs/current/xfunc-volatility.html
    """

    IMMUTABLE = "i"
    STABLE = "s"
    VOLATILE = "v"


class ParallelSafety(generic.AliasEnum):
    """Postgres parallel safety, as described in
    https://www.postgresql.org/docs/current/parallel-safety.html
    """

    SAFE = "s"
    RESTRICTED = "r"
    UNSAFE = "u"


class _BaseProcedure(generic._DynamicObject, generic._CollectionChild):
    """Postgres Procedure base object. Represents a stored procedure,
    function, window function or aggregate on a Postgres server.

    Args:
        name (str): name of the procedure
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Procedure owner
        kind (str): Procedure kind (FUNCTION/PROCEDURE/AGGREGATE/WINDOW FUNCTION)
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID
        parent (ProcedureCollection): parent collection

    Attributes:
        name (str): Procedure name
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Procedure owner
        kind (str): Procedure kind (FUNCTION/PROCEDURE/AGGREGATE/WINDOW FUNCTION)
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID
    """

    def __init__(
        self,
        name: str,
        kind: str,
        schema: str = "public",
        argument_types: List[str] = None,
        oid: Optional[int] = None,
        parent: "ProcedureCollection" = None,
        owner: str = None,
        cluster: "Cluster" = None,
        language: str = "sql",
        security_definer: bool = False,
        strict: bool = False,
        leak_proof: bool = False,
        volatility: Volatility = Volatility.VOLATILE,
        parallel_mode: ParallelSafety = ParallelSafety.UNSAFE,
    ):
        super().__init__(kind=kind, cluster=cluster, oid=oid, name=name, schema=schema)
        generic._CollectionChild.__init__(self, parent=parent)
        self._language = language
        self._owner = owner
        self._security_definer = security_definer
        self._leak_proof = leak_proof
        self._strict = strict
        self._volatility = Volatility(volatility)
        self._parallel_mode = ParallelSafety(parallel_mode)
        self._argument_types = argument_types

    def _sql_fqn(self) -> Composable:
        """In a form of: schema.function (arg1, arg2)"""
        fqn = super()._sql_fqn()
        if self._argument_types:
            fqn = fqn + SQL(" (") + SQL(",").join([Identifier(x) for x in self._argument_types]) + SQL(")")
        return fqn

    @property
    def security_definer(self) -> bool:
        return self._security_definer

    @property
    def leak_proof(self) -> bool:
        return self._leak_proof

    @property
    def strict(self) -> bool:
        return self._strict

    @property
    def volatility(self) -> Volatility:
        return self._volatility

    @property
    def parallel_mode(self) -> ParallelSafety:
        return self._parallel_mode

    @property
    def argument_types(self) -> Optional[List[str]]:
        return self._argument_types

    @property
    def language(self) -> str:
        return self._language

    def drop(self, cascade: bool = False):
        """Drops the procedure from the database

        Args:
            cascade (bool): cascade dependent objects
        """

        sql = SQL(f"DROP {self.kind} {{procedure}}").format(procedure=self._sql_fqn())
        if cascade:
            sql += SQL(" CASCADE")
        self.cluster.execute(sql)

    def refresh(self):
        """Re-initialize the object, refreshing its properties from the database"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_procedure", self.cluster.version) + SQL(" AND p.oid = %s")
            result = self.cluster.execute(sql, (self.oid))
            if not result:
                raise PostgresError("Procedure with oid %s was not found", self.oid)
            mapper = _ProcedureMapper(result[0])
            mapper.map(self)

    @property
    def owner(self) -> Optional[str]:
        return self._owner

    @owner.setter
    def owner(self, owner: str):
        generic._set_ephemeral_attr(self, "owner", owner)

    @property
    def schema(self) -> Optional[str]:
        return self._schema

    @schema.setter
    def schema(self, schema: str):
        generic._set_ephemeral_attr(self, "schema", schema)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str):
        generic._set_ephemeral_attr(self, "name", name)


class Procedure(_BaseProcedure):
    """Postgres Procedure object. Represents a stored procedure on a Postgres server.

    Args:
        name (str): name of the procedure
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Procedure owner
        security_definer (bool): Whether the procedure is a security definer
        leak_proof (bool): Whether the procedure is leak proof
        strict (bool): Whether the procedure is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID

    Attributes:
        name (str): Procedure name
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Procedure owner
        kind (str): Procedure kind (FUNCTION/PROCEDURE/AGGREGATE/WINDOW FUNCTION)
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID
    """

    def __init__(self, *args, **kwargs):
        super().__init__(kind=ProcedureKind.PROCEDURE.name, *args, **kwargs)


class Function(_BaseProcedure):
    """Postgres Function object. Represents a function on a Postgres server.

    Args:
        name (str): name of the function
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Function owner
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID

    Attributes:
        name (str): Procedure name
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Procedure owner
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID
    """

    def __init__(self, *args, **kwargs):
        super().__init__(kind=ProcedureKind.FUNCTION.name, *args, **kwargs)


class WindowFunction(_BaseProcedure):
    """Postgres Window Function object. Represents a window function on a Postgres server.

    Args:
        name (str): name of the function
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Function owner
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID

    Attributes:
        name (str): Procedure name
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Procedure owner
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID
    """

    def __init__(self, *args, **kwargs):
        super().__init__(kind=ProcedureKind.WINDOW_FUNCTION.name, *args, **kwargs)


class Aggregate(_BaseProcedure):
    """Postgres Aggregate object. Represents an aggregate on a Postgres server.

    Args:
        name (str): name of the aggregate function
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Function owner
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID


    Attributes:
        name (str): Procedure name
        cluster (str): Postgres cluster object
        schema (str): Schema name
        owner (str): Procedure owner
        security_definer (bool): Whether the function is a security definer
        leak_proof (bool): Whether the function is leak proof
        strict (bool): Whether the function is strict
        volatility (Volatility): Volatility mode (IMMUTABLE/STABLE/VOLATILE)
        parallel_mode (ParallelSafety): Parallel mode (SAFE/RESTRICTED/UNSAFE)
        argument_types (List[str]): A list of argument types, if any
        oid (int): Procedure OID
    """

    def __init__(self, *args, **kwargs):
        super().__init__(kind=ProcedureKind.AGGREGATE.name, *args, **kwargs)


class _ProcedureMapper(generic._BaseObjectMapper[_BaseProcedure]):
    """Maps out a resultset from a database query to a procedure object"""

    attributes = [
        "oid",
        "name",
        "schema",
        "owner",
        "language",
        "kind",
        "security_definer",
        "leak_proof",
        "strict",
        "volatility",
        "parallel_mode",
        "argument_types",
    ]
    exclude = ["kind", "volatility", "parallel_mode"]

    def map(self, obj: _BaseProcedure) -> _BaseProcedure:
        """Assigns attributes to the Postgres procedure based on
        the definition resultset and returns the object.

        Args:
            obj (_ProcedureBase): Postgres procedure object
        """
        super().map(obj)
        obj._volatility = Volatility(self["volatility"])
        obj._parallel_mode = ParallelSafety(self["parallel_mode"])

        return obj


class ProcedureVariations(List[_BaseProcedure], generic._ClusterBound):
    """A list of procedures with the same name, but variable argument sets."""

    def __init__(self, cluster: "Cluster"):
        super().__init__()
        generic._ClusterBound.__init__(self, cluster=cluster)


_procedure_kinds: Dict[str, Type[_BaseProcedure]] = {
    "f": Function,
    "p": Procedure,
    "w": WindowFunction,
    "a": Aggregate,
}


class ProcedureCollection(generic._BaseCollection[ProcedureVariations]):
    """An iterable collection of procedure variations indexed by procedure name.
    For procedures outside of the 'public' schema, index becomes "schemaname.procedurename".
    Procedure variations contains all procedures with the same name, yet different
    set of arguments.
    """

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and retrieves objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_procedure", self.cluster.version) + SQL(
            " ORDER BY proname, schemaname, proargtypes"
        )
        result = self.cluster.execute(sql)
        if result:
            mappers = [_ProcedureMapper(x) for x in result]
            # group by schema and name for index access, then put each group into a ProcedureVariations list
            grouped_by_index = util.group_by(
                lambda x: self._index(name=x["name"], schema=x["schema"]), mappers
            )
            for key, mapper_group in grouped_by_index.items():
                self[key] = ProcedureVariations(cluster=self.cluster)
                for mapper in mapper_group:
                    kind = mapper["kind"]
                    try:
                        proc_class = _procedure_kinds[kind]
                    except KeyError:
                        raise PostgresError(f"Unknown procedure kind: {kind}")
                    proc = proc_class(
                        name=mapper["name"],
                        schema=mapper["schema"],
                        oid=mapper["oid"],
                        cluster=self.cluster,
                        parent=self,
                    )
                    self[key].append(mapper.map(proc))
