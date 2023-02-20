"""Cluster base object

Cluster object is your interface to all the Managed Objects and other features of PGMob. You use it to connect to your PostgreSQL
server using the adapter, such as ``psycopg2``. A connected Cluster object gives you the following capabilities:

- Managing server connections
- Managing database objects (current database only)
- Execute ad-hoc SQL queries and shell commands
- Run backup/restore operations
"""
import logging
from typing import Any, Callable, List, Optional, Tuple, Union

from .os import _BaseShellEnv, ShellEnv, OSCommandResult
from ._decorators import RefreshProperty, LAZY_PREFIX, get_lazy_property
from .errors import *
from .adapters import detect_adapter, NoResultsToFetch, AdapterError
from .sql import SQL, Composable, Identifier, Literal
from .adapters.base import BaseAdapter, BaseCursor
from . import objects
from . import util

LOGGER = logging.getLogger(__name__)


class _NoAutocommitContextManager(object):
    def __init__(self, cluster: "Cluster"):
        self.cluster = cluster
        self.autocommit = self.cluster.adapter.get_autocommit()

    def __enter__(self):
        if self.autocommit:
            self.cluster.adapter.set_autocommit(False)
            return self.cluster

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cluster.adapter.commit()
        if self.autocommit:
            self.cluster.adapter.set_autocommit(True)


class Cluster(object):
    """Provides a management interface for postgres cluster configuration.

    Args:
        connection(Any): a connection object. Overrides other connectivity args.
        become(str): become this role after connecting. Executes SET ROLE <rolename>
        adapter(adapters.BaseAdapter): Postgres connectivity Adapter object. Defines which underlying driver
            to be used for database communications.
        *args: underlying adapter connection parameters
        **kwargs: underlying adapter connection parameters

    Attributes:
        become(str): become this role after connecting. Executes SET ROLE <rolename>
        current_database(str): Database name, to which the connection is currently established
        adapter(BaseAdapter): Postgres connectivity Adapter object. Defines which underlying driver
            to be used for database communications.


    Examples:
        To connect to the PostgreSQL server use the same arguments as you would when using an
        underlying adapter, such as `psycopg2`_:

        >>> cluster = Cluster(host="127.0.0.1", user="postgres", password="s3cur3p@ss")  # doctest: +SKIP

        Validate that the adapter is connected:

        >>> cluster.adapter.is_connected
        True

        .. _psycopg2:
            https://www.psycopg.org/docs/

    """

    def __init__(
        self,
        connection=None,
        become=None,
        adapter: BaseAdapter = None,
        shell: Optional[_BaseShellEnv] = None,
        *args,
        **kwargs
    ):
        self.shell = shell if shell else ShellEnv()
        self.adapter: BaseAdapter = adapter if adapter else detect_adapter()
        self.become = become
        if connection:
            self.adapter.connection = connection
        else:
            self.adapter.connect(*args, **kwargs)
        self._acquire_connection()

    def __del__(self):
        if self.adapter.is_connected:
            self.adapter.close_connection()

    def _initialize(self):
        init_data = self.execute(SQL("SELECT current_database(), version()"))
        if len(init_data) > 0:
            self.current_database = init_data[0][0]
            dbms, version_string = init_data[0][1].split()[0:2]
            if dbms != "PostgreSQL":
                raise PostgresError("DBMS is not postgres, version not supported")
            version = util.Version(version_string)
            if version < util.Version("10.0"):
                raise PostgresError("Versions lower than 10.0 are not supported")
            self.version = version

    def _validate_connection(self):
        return self.adapter.is_connected

    def _acquire_connection(self):
        if self._validate_connection():
            self.adapter.set_autocommit(True)
            # check if the session needs to execute "set role"
            self._become_role()
            self._initialize()
        else:
            raise PostgresError("Failed to validate the connection")

    def _become_role(self):
        if self.become:
            activate_sql = SQL("SET ROLE {role}").format(role=Identifier(self.become))
            self.execute(activate_sql)

    def _no_autocommit(self):
        return _NoAutocommitContextManager(cluster=self)

    def execute_with_cursor(self, task: Callable[[BaseCursor], Any], *args, **kwargs) -> Any:
        """Executes a task against a cursor. Transaction would be automatically committed upon finish.

        Args:
            task (Callable[[BaseCursor], Any]): callable with cursor object as an only argument

        Returns:
            Optional[List[Tuple[Any]]]]: List of tuples returned from the server or None if no rows selected.

        Example:
            Run a task that fetches a row from a cursor

            >>> def task(cursor):
            ...     cursor.execute("SELECT 1, 2")
            ...     return cursor.fetchone()
            >>> cluster.execute_with_cursor(task)
            (1, 2)
        """
        # check our connection, reconnect if necessary
        if self._validate_connection():
            with self.adapter.cursor() as cursor:
                result = task(cursor, *args, **kwargs)
            if self.adapter.is_in_transaction:
                self.adapter.commit()
            return result
        else:
            raise PostgresError("Connection is not open")

    def refresh(self):
        """Refresh dynamic properties of the object. They will be retrieved from the Postgres cluster next time they are called.

        Example:
            Refresh cluster objects after dropping a database

            >>> db = "somedb"  # doctest: +SKIP
            >>> cluster.databases[db].drop()  # drop the database from the server
            >>> db in cluster.databases  # the database is still in the local cache
            True
            >>> cluster.refresh()
            >>> db in cluster.databases
            False
        """

        # mark all lazy attributes for refresh
        lazy_attributes = dir(self)
        for attr in [attr for attr in lazy_attributes if attr.startswith(LAZY_PREFIX)]:
            setattr(self, attr, RefreshProperty())

    def execute(
        self, query: Union[Composable, str], params: Union[Tuple[Any], Any] = None
    ) -> List[Tuple[Any]]:
        """Execute a query against Postgres server. Transaction would be automatically committed upon completion.

        Args:
            query (Union[Composable, str]): Query text or a Composable object
            params (Union[Tuple[Any], Any]): Tuple of parameter values (or a single value) to replace parameters in the query

        Returns:
            List[Tuple[Any]]]: List of tuples returned from the server, or empty list if no rows were selected.

        Raises:
            AdapterError: Whenever the adapter returns an error.

        Example:
            To execute a simple query with parameters, pass the parameters either as a tuple or as *args:

            >>> cluster.execute("SELECT schemaname, viewowner FROM pg_views WHERE viewname = %s", "pg_tables")
            [('pg_catalog', 'postgres')]
            >>> cluster.execute("SELECT schemaname, viewowner FROM pg_views WHERE viewname = ANY(%s)", (["pg_tables", "pg_views"], ))
            [('pg_catalog', 'postgres'), ('pg_catalog', 'postgres')]
            >>> cluster.execute("SELECT schemaname, viewowner FROM pg_views WHERE 1=2")
            []

            You can also use Composable objects to properly handle identifiers and literals in your SQL code:
            >>> from pgmob.sql import SQL, Identifier, Literal
            >>> sql = SQL("SELECT schemaname, viewowner FROM {table} WHERE viewname = %s").format(table=Identifier("pg_views"))
            >>> cluster.execute(sql, "pg_tables")
            [('pg_catalog', 'postgres')]
            >>> sql = SQL("SET LOCAL TIME ZONE {tz}").format(tz=Literal("PST8PDT"))
            >>> cluster.execute(sql)
            []
        """

        LOGGER.debug("Executing query: %s", query)

        def execute_task(cursor: BaseCursor) -> Optional[List[Tuple[Any]]]:
            if params:
                param_set = params if isinstance(params, tuple) else tuple([params])
            else:
                param_set = None
            cursor.execute(query, param_set)
            if cursor.statusmessage:
                try:
                    return cursor.fetchall()
                except NoResultsToFetch:
                    return []
            else:
                return []

        return self.execute_with_cursor(execute_task)

    def terminate(
        self,
        all_connections: bool = None,
        databases: List[str] = None,
        pids: List[int] = None,
        roles: List[str] = None,
        exclude_roles: List[str] = None,
        exclude_databases: List[str] = None,
        exclude_pids: List[int] = None,
    ) -> List[int]:
        """Terminates connections based on provided parameters. Will avoid terminating system PIDs and self.

        Args:
            databases (List[str]): names of target databases
            roles (List[str]): roles which connections should be terminated
            pids (List[int]): pids to terminate
            exclude_roles (List[str]): roles to exclude
            exclude_databases (List[str]): databases to exclude
            exclude_pids (List[str]): pids to exclude
            all_connections (bool): terminate all connections (except own and system PIDs)

        Returns:
            List[int]: PIDs of the terminated connections

        Example:
            Terminate connections from a specific role to a specific database

            >>> cluster.terminate(databases=["somedb"], roles=["someapp"])
            []
        """

        # at least one parameter should specified
        if not (databases or exclude_roles or pids or roles or all_connections):
            raise ValueError("At least one parameter should be specified")

        # builds dynamic in statements from arrays
        def join_sql_in(sql, in_members):
            return SQL(sql).format(SQL(", ").join([Literal(x) for x in in_members]))

        sql = SQL("SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity WHERE {where}")
        params: List[Tuple[Union[str, int], ...]] = []
        # start collecting where clauses depending on parameters
        # never allow killing system processes or self
        where = [
            SQL("pid <> pg_backend_pid()"),
            SQL("backend_type IN ('client backend', 'walsender')"),
        ]
        # filter connections by parameters
        if databases:
            where.append(SQL("datname in %s"))
            params.append(tuple(databases))
        if roles:
            where.append(SQL("usename in %s"))
            params.append(tuple(roles))
        if pids:
            where.append(SQL("pid in %s"))
            params.append(tuple(pids))
        if exclude_databases:
            where.append(SQL("datname not in %s"))
            params.append(tuple(exclude_databases))
        if exclude_roles:
            where.append(SQL("usename not in %s"))
            params.append(tuple(exclude_roles))
        if exclude_pids:
            where.append(SQL("pid not in %s"))
            params.append(tuple(exclude_pids))
        # join where clauses using AND
        formatted_sql = sql.format(where=SQL(" AND ").join(where))
        terminated_pids: List[int] = []
        result = self.execute(formatted_sql, tuple(params))
        if result:
            terminated_pids.extend([x[0] for x in result])
        return terminated_pids

    def run_os_command(self, command: str, raise_exception=True) -> OSCommandResult:
        """Runs an OS command by reading output from a binary exectuted via COPY FROM command.
        The command string would be put into an EOF block. Make sure to follow shell symbol escape rules.

        Args:
            command (str): command to execute
            raise_exception (bool): raise PostgresShellCommandError when command returns a non-zero exit code

        Returns:
            OSCommandResult: command execution results

        Raises:
            PostgresShellCommandError: on non-zero exit code when raise_exception == True

        Example:
            Run the command and return results

            >>> iam = cluster.run_os_command("whoami")
            >>> iam.exit_code
            0
            >>> iam.text
            'postgres'
        """
        template = self.shell.get_os_command_wrapper()
        do_block = util.get_sql("execute_os_command")

        def task(cursor: BaseCursor) -> OSCommandResult:
            cursor.execute(
                """
                CREATE TEMPORARY TABLE command_output(
                id int GENERATED ALWAYS AS IDENTITY,
                msg text
            );
            """
            )
            output = OSCommandResult(command=command)
            try:
                cursor.execute(do_block, (template.format(command=command),))
                cursor.execute("SELECT msg FROM command_output ORDER BY id;")
                if cursor.statusmessage:
                    result = cursor.fetchall()
                    # line 1 is exit code, the rest of the lines - stdout + stderr
                    if len(result) > 1:
                        output.text = "\n".join([x[0] for x in result[1:]])
                    else:
                        output.text = ""
                    output.exit_code = result[0][0]
                else:
                    raise PostgresError("Failed to retrieve errorcode from the OS")
                if raise_exception:
                    output.raise_for_error()
            except NoResultsToFetch:
                raise PostgresError("Did not receive any results")
            finally:
                cursor.execute("DROP TABLE command_output;")

            return output

        try:
            return self.execute_with_cursor(task)
        except AdapterError as e:
            raise PostgresError("Failed to execute %s with message: %s", command, e)

    def reload(self) -> bool:
        """Reload PostgreSQL configuration by executing pg_reload_conf()

        Returns:
            bool: whether configuration reload was successful

        Example:
            Reload PostgreSQL configuration

            >>> cluster.reload()
            True
        """
        result = self.execute(SQL("SELECT pg_reload_conf()"))
        if result:
            return result[0][0]
        else:
            raise PostgresError("Failed to retrieve results")

    @property
    def roles(self) -> objects.RoleCollection:
        """Postgres role objects

        Example:
            Create a new role:

            >>> owner_role = cluster.roles.new(name="db1owner", password="foobar")
            >>> owner_role.create()
            >>> cluster.roles.refresh()
            >>> "db1owner" in cluster.roles
            True

            Clone an existing role

            >>> sql = cluster.roles["db1owner"].script().decode("utf8").replace("db1owner", "newrole")
            >>> cluster.execute(sql)
            []
            >>> cluster.refresh()
            >>> cluster.roles["newrole"]
            Role('newrole')
        """
        return get_lazy_property(self, "roles", lambda: objects.RoleCollection(cluster=self))

    @property
    def databases(self) -> objects.DatabaseCollection:
        """Postgres database objects

        Example:
            Reassign database ownership:
            >>> db = "somedatabase"  # doctest: +SKIP
            >>> role = "someotherrole"  # doctest: +SKIP
            >>> cluster.databases[db].owner = role
            >>> cluster.databases[db].alter()
            >>> cluster.databases[db].refresh()
            >>> cluster.databases[db].owner == role
            True
        """
        return get_lazy_property(self, "databases", lambda: objects.DatabaseCollection(cluster=self))

    @property
    def sequences(self) -> objects.SequenceCollection:
        """Postgres sequence objects

        Example:
            Retrieving sequences from the server

            >>> cluster.execute("CREATE SEQUENCE seq1")
            []
            >>> cluster.sequences['seq1']
            Sequence('seq1')
            >>> cluster.sequences['seq1'].owner
            'postgres'
        """
        return get_lazy_property(self, "sequences", lambda: objects.SequenceCollection(cluster=self))

    @property
    def tables(self) -> objects.TableCollection:
        """Postgres table objects

        Example:
            Retrieving tables from the server after refreshing table objects

            >>> cluster.execute("CREATE TABLE tab1(a int)")
            []
            >>> cluster.tables.refresh()
            >>> cluster.tables['tab1']
            Table('tab1')
            >>> cluster.tables['tab1'].owner
            'postgres'
        """
        return get_lazy_property(self, "tables", lambda: objects.TableCollection(cluster=self))

    @property
    def replication_slots(self) -> objects.ReplicationSlotCollection:
        """Postgres replication slot objects"""
        return get_lazy_property(
            self, "replication_slots", lambda: objects.ReplicationSlotCollection(cluster=self)
        )

    @property
    def hba_rules(self) -> objects.HBARuleCollection:
        """Postgres HBA rules

        Allows you to modify pg_hba on the fly by comparing, adding, and removing entries
        from the pg_hba file.

        Example:
            Adding an entry to pg_hba

            >>> entry = "host all postgres 127.0.0.1/32 trust"
            >>> entry in cluster.hba_rules
            False
            >>> cluster.hba_rules.extend(entry)
            >>> cluster.hba_rules.alter()
        """
        return get_lazy_property(self, "hba_rules", lambda: objects.HBARuleCollection(cluster=self))

    @property
    def procedures(self) -> objects.ProcedureCollection:
        """Postgres procedures, functions, aggregates and window functions

        Example:
            Retrieving procedures from the server

            >>> cluster.execute("CREATE FUNCTION foo () RETURNS int AS 'SELECT 1' LANGUAGE SQL")
            []
            >>> cluster.execute("CREATE FUNCTION foo (int) RETURNS int AS 'SELECT 1' LANGUAGE SQL")
            []
            >>> cluster.procedures['foo']
            [Function('foo'), Function('foo')]
        """
        return get_lazy_property(self, "procedures", lambda: objects.ProcedureCollection(cluster=self))

    @property
    def views(self) -> objects.ViewCollection:
        """Postgres views

        Example:
            Retrieving views from the server

            >>> cluster.execute("CREATE VIEW v1 AS SELECT 1")
            []
            >>> cluster.views['v1']
            View('v1')
            >>> cluster.views['v1'].owner
            'postgres'
        """
        return get_lazy_property(self, "views", lambda: objects.ViewCollection(cluster=self))

    @property
    def schemas(self) -> objects.SchemaCollection:
        """Postgres schema objects

        Example:
            Migrate tables from one schema to another

            >>> schema = "myschema"  # doctest: +SKIP
            >>> new_schema = "app_schema"
            >>> cluster.schemas.new(new_schema).create()
            >>> for t in [t for t in cluster.tables if t.schema == schema]:
            ...     t.schema = new_schema
            ...     t.alter()
        """
        return get_lazy_property(self, "schemas", lambda: objects.SchemaCollection(cluster=self))

    @property
    def large_objects(self) -> objects.LargeObjectCollection:
        """Postgres large objects"""
        return get_lazy_property(self, "large_objects", lambda: objects.LargeObjectCollection(cluster=self))

    def reassign_owner(self, new_owner: str, owner: str = None, objects: list = None):
        """Reassigns ownership of Postgres objects.
        When "objects" parameter is provided, only the ownership for those objects will be changed.
        When both "owner" and "new_owner" are specified, reassigns ownership of all objects owned by "owner".
        This includes database ownership.

        Arguments:
            new_owner (str): new owner name
            owner (str): old owner name
            objects (list): An iterable containing pgcmo objects, such as tables or databases.

        Raises:
            AttributeError: when neither owner nor objects is specified.
        """

        new_owner_role = self.roles[new_owner]

        def get_change(obj):
            """Grab changes from objects that require ownership change"""
            if obj.owner != new_owner_role.name:
                obj.owner = new_owner_role.name
                return obj._changes
            else:
                return []

        if objects:
            changes = []
            for obj in objects:
                changes.extend(get_change(obj))

            # merge sql code from all pending changes into a single statement,
            # limited by 30k params in one go, and execute it
            statements = []
            parameters: List[tuple] = []
            while changes:
                change = changes.pop(0)
                statements.append(change.sql)
                if change.params:
                    if isinstance(change.params, tuple):
                        parameters.extend(change.params)
                    else:
                        parameters.append(change.params)
                if not changes or len(parameters) > 30000:
                    self.execute(SQL(";\n").join(statements), tuple(parameters))
                    statements.clear()
                    parameters.clear()

        elif owner:
            owner_role = self.roles[owner]
            self.execute(
                SQL("REASSIGN OWNED BY {old} TO {new}").format(
                    old=owner_role._sql_fqn(), new=new_owner_role._sql_fqn()
                )
            )

        else:
            raise AttributeError("Either current owner or object list should be specified")
