"""Backup and Restore tools

In order to execute a backup or a restore operation, PGMob would issue a ``pg_dump``/``pg_restore`` command
on a remote server spawned as a subprocess of the PostgreSQL process. The binary should be available on the
server (you can specify an exact path) and should be able to connect to localhost without a password.

Example:
    Create a backup from one database and restore it as a different database

    >>> old_db = "foo"  # doctest: +SKIP
    >>> new_db = "bar"  # doctest: +SKIP
    >>> file_backup = FileBackup(cluster=cluster)
    >>> file_backup.backup(database=old_db, path="/tmp/db.bak")
    >>> file_restore = FileRestore(cluster=cluster)
    >>> file_restore.restore(database=new_db, path="/tmp/db.bak")
"""
from typing import List, Optional
import logging
from pathlib import Path
from .os import ShellEnv, _BaseShellEnv
from . import cluster

LOGGER = logging.getLogger(__name__)


class _CommonOptions(object):
    """Common backup/restore options"""

    def __init__(self, shell: Optional[_BaseShellEnv] = None, **kwargs) -> None:
        self.shell = shell if shell else ShellEnv()
        self._add_if_exists = False
        self._clean = False
        self._create = False
        self._data_only = False
        self._exclude_schemas: List[str] = []
        self._format: Optional[str] = None
        self._no_privileges = False
        self._no_publications = False
        self._no_subscriptions = False
        self._no_tablespaces = False
        self._no_owner = False
        self._schema_only = False
        self._schemas: List[str] = []
        self._section: Optional[str] = None
        self._set_role: Optional[str] = None
        self._strict_names = False
        self._superuser: Optional[str] = None
        self._tables: List[str] = []
        self._verbose = False

        for k, v in kwargs.items():
            if getattr(self, "_" + k):
                setattr(self, "_" + k, v)
            else:
                raise AttributeError("Unknown attribute: %s", k)

    # enforcing propert data types

    @property
    def add_if_exists(self) -> bool:
        return self._add_if_exists

    @add_if_exists.setter
    def add_if_exists(self, value: bool) -> None:
        self._add_if_exists = value

    @property
    def clean(self) -> bool:
        return self._clean

    @clean.setter
    def clean(self, value: bool) -> None:
        self._clean = bool(value)

    @property
    def create(self) -> bool:
        return self._create

    @create.setter
    def create(self, value: bool) -> None:
        self._create = bool(value)

    @property
    def data_only(self) -> bool:
        return self._data_only

    @data_only.setter
    def data_only(self, value: bool) -> None:
        self._data_only = bool(value)

    @property
    def exclude_schemas(self) -> List[str]:
        return self._exclude_schemas

    @exclude_schemas.setter
    def exclude_schemas(self, value: List[str]) -> None:
        self._exclude_schemas = [str(x) for x in value]

    @property
    def format(self) -> Optional[str]:
        return self._format

    @format.setter
    def format(self, value: Optional[str]) -> None:
        self._format = str(value) if value else None

    @property
    def no_privileges(self) -> bool:
        return self._no_privileges

    @no_privileges.setter
    def no_privileges(self, value: bool) -> None:
        self._no_privileges = bool(value)

    @property
    def no_publications(self) -> bool:
        return self._no_publications

    @no_publications.setter
    def no_publications(self, value: bool) -> None:
        self._no_publications = bool(value)

    @property
    def no_subscriptions(self) -> bool:
        return self._no_subscriptions

    @no_subscriptions.setter
    def no_subscriptions(self, value: bool) -> None:
        self._no_subscriptions = bool(value)

    @property
    def no_tablespaces(self) -> bool:
        return self._no_tablespaces

    @no_tablespaces.setter
    def no_tablespaces(self, value: bool) -> None:
        self._no_tablespaces = bool(value)

    @property
    def no_owner(self) -> bool:
        return self._no_owner

    @no_owner.setter
    def no_owner(self, value: bool) -> None:
        self._no_owner = bool(value)

    @property
    def schema_only(self) -> bool:
        return self._schema_only

    @schema_only.setter
    def schema_only(self, value: bool) -> None:
        self._schema_only = bool(value)

    @property
    def schemas(self) -> List[str]:
        return self._schemas

    @schemas.setter
    def schemas(self, value: List[str]) -> None:
        self._schemas = [str(x) for x in value]

    @property
    def section(self) -> Optional[str]:
        return self._section

    @section.setter
    def section(self, value: Optional[str]) -> None:
        self._section = str(value) if value else None

    @property
    def set_role(self) -> Optional[str]:
        return self._set_role

    @set_role.setter
    def set_role(self, value: Optional[str]) -> None:
        self._set_role = str(value) if value else None

    @property
    def strict_names(self) -> bool:
        return self._strict_names

    @strict_names.setter
    def strict_names(self, value: bool) -> None:
        self._strict_names = bool(value)

    @property
    def superuser(self) -> Optional[str]:
        return self._superuser

    @superuser.setter
    def superuser(self, value: Optional[str]) -> None:
        self._superuser = str(value) if value else None

    @property
    def tables(self) -> List[str]:
        return self._tables

    @tables.setter
    def tables(self, value: List[str]) -> None:
        self._tables = [str(x) for x in value]

    @property
    def verbose(self) -> bool:
        return self._verbose

    @verbose.setter
    def verbose(self, value: bool) -> None:
        self._verbose = bool(value)

    def render_args(self) -> List[str]:
        """Renders options as command line arguments

        Returns:
            List[str]: list of command line arguments
        """
        options: List[str] = []
        if self.clean:
            options.append("--clean")
        if self.create:
            options.append("--create")
        if self.data_only:
            options.append("--data-only")
        if self.schema_only:
            options.append("--schema-only")
        if self.superuser:
            options.append(f"--superuser={self.shell.quote(self.superuser)}")
        for table in self.tables:
            options.append(f'--table="{self.shell.quote(table)}"')
        for schema in self.schemas:
            options.append(f'--schema="{self.shell.quote(schema)}"')
        for schema in self.exclude_schemas:
            options.append(f'--exclude-schema="{self.shell.quote(schema)}"')
        if self.no_privileges:
            options.append("--no-privileges")
        if self.no_subscriptions:
            options.append("--no-subscriptions")
        if self.no_publications:
            options.append("--no-publications")
        if self.no_tablespaces:
            options.append("--no-tablespaces")
        if self.format:
            options.append(f"--format={self.shell.quote(self.format)}")
        if self.set_role:
            options.append(f'--role="{self.shell.quote(self.set_role)}"')
        if self.add_if_exists:
            options.append("--if-exists")
        if self.strict_names:
            options.append("--strict-names")
        if self.verbose:
            options.append("--verbose")
        if self.section:
            options.append(f"--section={self.shell.quote(self.section)}")
        if self.no_owner:
            options.append("--no-owner")
        return options


class BackupOptions(_CommonOptions):
    """Parameters to be used for the pg_dump binary

    Class attributes match closely to those displayed by the "pg_dump --help" command.

    Args:
        shell (_BaseShellEnv):            shell processor that defines pathing and escaping for the current environment
        **kwargs (dict):                  any supporter attribute can be submitted as kwargs

    Attributes:
        shell (_BaseShellEnv):            shell processor that defines pathing and escaping for the current environment
        format (str):                     (c|d|t|p) output file format (custom(default), directory, tar, plain text)
        jobs (int):                       use this many parallel jobs to dump
        verbose (bool):                   verbose mode
        compress (int):                   (0-9) compression level for compressed formats
        lock_wait_timeout (int):          fail after waiting TIMEOUT for a table lock
        data_only (bool):                 dump only the data, not the schema
        clean (bool):                     clean (drop) database objects before recreating
        create (bool):                    include commands to create database in dump
        schemas (List[str]):              dump the named schemas only
        exclude_schemas (List[str]):      do NOT dump the named schemas
        no_owner (bool):                  skip restoration of object ownership in plain-text format
        schema_only (bool):               dump only the schema, no data
        superuser (str):                  superuser user name to use in plain-text format
        tables (List[str]):               dump the named tables only
        exclude_tables (List[str]):       do NOT dump the named tables
        no_privileges (bool):             do not dump privileges (grant/revoke)
        exclude_table_data (List[str]):   do NOT dump data for the named table(s)
        add_if_exists (bool):             use IF EXISTS when dropping objects
        as_inserts (bool):                dump data as INSERT commands, rather than COPY
        no_subscriptions (bool):          do not dump subscriptions
        no_publications (bool):           do not dump publications
        no_tablespaces (bool):            do not dump tablespace assignments
        section (str):                    dump named section (pre-data, data, or post-data)
        strict_names (bool):              require table and/or schema include patterns to match at least one entity each
        set_role (str):                   invoke SET ROLE before dump
        blobs (bool):                     Include large objects in the dump
    """

    def __init__(self, shell: Optional[_BaseShellEnv] = None, **kwargs) -> None:
        self._compress = False
        self._compression_level = 5
        self._exclude_tables: List[str] = []
        self._exclude_table_data: List[str] = []
        self._as_inserts = False
        self._create_database = False
        self._lock_wait_timeout: Optional[int] = None
        self._blobs: Optional[bool] = None
        super().__init__(shell=shell, **kwargs)
        self.format = "c"

    @property
    def compress(self) -> bool:
        return self._compress

    @compress.setter
    def compress(self, value: bool) -> None:
        self._compress = bool(value)

    @property
    def as_inserts(self) -> bool:
        return self._as_inserts

    @as_inserts.setter
    def as_inserts(self, value: bool) -> None:
        self._as_inserts = bool(value)

    @property
    def create_database(self) -> bool:
        return self._create_database

    @create_database.setter
    def create_database(self, value: bool) -> None:
        self._create_database = bool(value)

    @property
    def compression_level(self) -> int:
        return self._compression_level

    @compression_level.setter
    def compression_level(self, value: int) -> None:
        self._compression_level = int(value)

    @property
    def exclude_tables(self) -> List[str]:
        return self._exclude_tables

    @exclude_tables.setter
    def exclude_tables(self, value: List[str]) -> None:
        self._exclude_tables = [str(x) for x in value]

    @property
    def exclude_table_data(self) -> List[str]:
        return self._exclude_table_data

    @exclude_table_data.setter
    def exclude_table_data(self, value: List[str]) -> None:
        self._exclude_table_data = [str(x) for x in value]

    @property
    def lock_wait_timeout(self) -> Optional[int]:
        return self._lock_wait_timeout

    @lock_wait_timeout.setter
    def lock_wait_timeout(self, value: Optional[int]) -> None:
        self._lock_wait_timeout = None if value is None else int(value)

    @property
    def blobs(self) -> Optional[bool]:
        return self._blobs

    @blobs.setter
    def blobs(self, value: Optional[bool]) -> None:
        self._blobs = None if value is None else bool(value)

    def render_args(self):
        """Renders options as command line arguments

        Returns:
            List[str]: A list of command line arguments
        """

        options = super().render_args()
        if self.compress:
            options.append(f"--compress={int(self.compression_level)}")
        if self.blobs is not None:
            options.append("--blobs" if self.blobs else "--no-blobs")
        if self.lock_wait_timeout:
            options.append(f"--lock-wait-timeout={int(self.lock_wait_timeout)}")
        if self.as_inserts:
            options.append("--inserts")
        if self.create_database:
            options.append("--create")
        for table in self.exclude_tables:
            options.append(f'--exclude-table="{table}"')
        for table in self.exclude_table_data:
            options.append(f'--exclude-table-data="{table}"')
        return options


class RestoreOptions(_CommonOptions):
    """Parameters to be used for the pg_restore binary

    Class attributes match closely to those displayed by the "pg_restore --help" command.

    Args:
        shell (_BaseShellEnv):            shell processor that defines pathing and escaping for the current environment
        **kwargs (dict):                  any supporter attribute can be submitted as kwargs

    Attributes:
        shell (_BaseShellEnv):            shell processor that defines pathing and escaping for the current environment
        format (str):                     (c|d|t) backup file format (should be automatic)
        jobs (int):                       use this many parallel jobs to restore
        verbose (bool):                   verbose mode
        data_only (bool):                 restore only the data, no schema
        clean (bool):                     clean (drop) database objects before recreating
        create (bool):                    create the target database
        exit_on_error (bool):             exit on error, default is to continue
        indexes (List[str]):              restore named indexes
        schemas (List[str]):              restore only objects in these schemas
        exclude_schemas (List[str]):      do not restore objects in these schemas
        use_list (str):                   use table of contents from this file for selecting/ordering output
        no_owner (bool):                  skip restoration of object ownership
        functions (List[str]):            (NAME(args)) restore named functions
        schema_only (bool):               restore only the schema, no data
        superuser (str):                  superuser user name to use for disabling triggers
        tables (List[str]):               restore named relations (table, view, etc.)
        triggers (List[str]):             restore named triggers
        no_privileges (bool):             skip restoration of access privileges (grant/revoke)
        single_transaction (bool):        restore as a single transaction
        disable_triggers (bool):          disable triggers during data-only restore
        add_if_exists (bool):             use IF EXISTS when dropping objects
        no_subscriptions (bool):          do not restore subscriptions
        no_publications (bool):           do not restore publications
        no_tablespaces (bool):            do not restore tablespace assignments
        section (str):                    restore named section (pre-data, data, or post-data)
        no_data_for_failed_tables (bool): do not restore data of tables that could not be created
        strict_names (bool):              require table and/or schema include patterns to match at least one entity each
        set_role (str):                   invoke SET ROLE before dump
    """

    def __init__(self, shell: Optional[_BaseShellEnv] = None, **kwargs) -> None:
        self._exit_on_error = False
        self._indexes: List[str] = []
        self._functions: List[str] = []
        self._triggers: List[str] = []
        self._jobs: Optional[int] = None
        self._use_list: Optional[str] = None
        self._single_transaction = False
        self._disable_triggers = False
        self._no_data_for_failed_tables = False
        super().__init__(shell=shell, **kwargs)

    @property
    def exit_on_error(self) -> bool:
        return self._exit_on_error

    @exit_on_error.setter
    def exit_on_error(self, value: bool) -> None:
        self._exit_on_error = bool(value)

    @property
    def indexes(self) -> List[str]:
        return self._indexes

    @indexes.setter
    def indexes(self, value: List[str]) -> None:
        self._indexes = [str(x) for x in value]

    @property
    def functions(self) -> List[str]:
        return self._functions

    @functions.setter
    def functions(self, value: List[str]) -> None:
        self._functions = [str(x) for x in value]

    @property
    def triggers(self) -> List[str]:
        return self._triggers

    @triggers.setter
    def triggers(self, value: List[str]) -> None:
        self._triggers = [str(x) for x in value]

    @property
    def jobs(self) -> Optional[int]:
        return self._jobs

    @jobs.setter
    def jobs(self, value: Optional[int]) -> None:
        self._jobs = int(value) if value else None

    @property
    def use_list(self) -> Optional[str]:
        return self._use_list

    @use_list.setter
    def use_list(self, value: Optional[str]) -> None:
        self._use_list = str(value) if value else None

    @property
    def single_transaction(self) -> bool:
        return self._single_transaction

    @single_transaction.setter
    def single_transaction(self, value: bool) -> None:
        self._single_transaction = bool(value)

    @property
    def disable_triggers(self) -> bool:
        return self._disable_triggers

    @disable_triggers.setter
    def disable_triggers(self, value: bool) -> None:
        self._disable_triggers = bool(value)

    @property
    def no_data_for_failed_tables(self) -> bool:
        return self._no_data_for_failed_tables

    @no_data_for_failed_tables.setter
    def no_data_for_failed_tables(self, value: bool) -> None:
        self._no_data_for_failed_tables = bool(value)

    def render_args(self):
        """Renders options as command line arguments

        Returns:
            List[str]: A list of command line arguments
        """
        options = super().render_args()
        if self.exit_on_error:
            options.append("--exit-on-error")
        for index in self.indexes:
            options.append(f'--index="{index}"')
        for function in self.functions:
            options.append(f'--function="{function}"')
        for trigger in self.triggers:
            options.append(f'--trigger="{trigger}"')
        if self.jobs:
            options.append(f"--jobs={int(self.jobs)}")
        if self.use_list:
            options.append(f"--use-list={self.use_list}")
        if self.single_transaction:
            options.append("--single-transaction")
        if self.disable_triggers:
            options.append("--disable-triggers")
        if self.no_data_for_failed_tables:
            options.append("--no-data-for-failed-tables")
        return options


class _BackupRestoreOperation(object):
    """Base backup/restore operation class that implements binary execution.

    Args:
        cluster (cluster.Cluster): Postgres cluster object
        binary_path (str): Path to the binary
        command (str): OS shell command to execute
        base_path (str): base path for the backups
        options (_CommonOptions): Options object
        shell (_BaseShellEnv): shell processor that defines pathing and escaping for the current environment
    """

    def __init__(
        self,
        cluster: cluster.Cluster,
        binary_path: str,
        command: str,
        base_path: str,
        options: _CommonOptions,
        shell: Optional[_BaseShellEnv] = None,
    ) -> None:
        self.shell = shell if shell else ShellEnv()
        self.command = command
        self.binary = binary_path
        self.cluster = cluster
        self.base_path = base_path.rstrip("/")
        self.on_start_commands: List[str] = []
        self.on_finish_commands: List[str] = []
        self.options = options

    def _exec_commands(self, commands: List[str], **kwargs):
        for command in commands:
            formatted_command = command.format(**kwargs)
            LOGGER.debug(f"Running {self.__class__.__name__} command: {formatted_command}")
            self.cluster.run_os_command(command=formatted_command)

    def execute_command(self, database: str, path: str):
        """Executes backup/restore commands and replaces the formatted commands with actual values.

        Args:
            database(str): database name
            path(str): backup path

        Returns:
            str: stdin and stdout of executed command
        """
        full_path = self.shell.join_path(self.base_path, path)
        params = dict(
            database=database,
            path=full_path,
            options=" ".join(self.options.render_args()),
            binary=self.binary,
            filename=Path(full_path).name,
        )
        self._exec_commands(self.on_start_commands, **params)
        try:
            result = self._exec_commands([self.command], **params)
        finally:
            self._exec_commands(self.on_finish_commands, **params)
        return result


class FileBackup(_BackupRestoreOperation):
    """File Backup class that performs a Backup operation to a local filesystem.
    Executes pg_dump on a target postgres cluster spawned as a subprocess of Postgres server process.

    Args:
        cluster (cluster.Cluster): Postgres cluster object
        base_path (str): Base backup path. If specified, the backup path would be considered relative to it.
        binary_path (str): Path to the pg_dump binary. Use when a specific binary version is needed or the binary is not in PATH.
        options (BackupOptions): backup options represented by BackupOptions class
        shell (_BaseShellEnv): shell processor that defines pathing and escaping for the current environment

    Attributes:
        options (BackupOptions): backup options represented by the BackupOptions class
        cluster (cluster.Cluster): Postgres cluster object
        binary (str): Path to the pg_dump binary
        shell (_BaseShellEnv): shell processor that defines pathing and escaping for the current environment
        on_start_commands (List[str]): commands to execute prior to launching the backup
        command (str): main backup command
        on_finish_commands (List[str]): commands to execute after backup is completed or failed

    Example:
        Backup a database schema for tables "a" and "b"

        >>> db = "foo"  # doctest: +SKIP
        >>> backup = FileBackup(cluster=cluster, base_path="/tmp")
        >>> backup.options.schema_only = True
        >>> backup.options.exclude_tables = ["a", "b"]
        >>> backup.backup(database=db, path=f"{db}.bak")
    """

    def __init__(
        self,
        cluster: cluster.Cluster,
        base_path: str = "",
        binary_path: str = "pg_dump",
        options: Optional[BackupOptions] = None,
        shell: Optional[_BaseShellEnv] = None,
    ):
        super().__init__(
            cluster=cluster,
            binary_path=binary_path,
            command='{binary} {options} -d "{database}" > "{path}"',
            base_path=base_path,
            options=options if options else BackupOptions(),
            shell=shell,
        )

    def backup(self, database, path):
        """Backup a database to the specified path

        Args:
            database (str):    name of the database to backup
            path (str):        path (relative or absolute) to backup to

        Returns:
            str: pg_dump stdout and stderr output
        """
        return self.execute_command(database=database, path=path)


class GCPBackup(FileBackup):
    """GCP Backup class that uploads backups to a GCP bucket.
    Executes "pg_dump" on a target postgres cluster spawned as a subprocess of Postgres server process.
    Requires "gsutil" command available on the server host.
    To configure authentication, run "gcloud auth login" under postgres OS user.

    Args:
        cluster (cluster.Cluster): Postgres cluster object
        bucket (str): (Optional) GCP bucket name to work with. If specified, the backup path would
            be considered relative of the bucket path
        binary_path (str): Path to the pg_dump binary. Use when a specific binary version is needed or the binary is not in PATH.
        options (BackupOptions): backup options represented by BackupOptions class
        shell (_BaseShellEnv): shell processor that defines pathing and escaping for the current environment

    Attributes:
        options (BackupOptions): backup options represented by the BackupOptions class
        cluster (cluster.Cluster): Postgres cluster object
        binary: Path to the pg_dump binary.
        on_start_commands (List[str]): commands to execute prior to launching the backup
        command (str): main backup command
        on_finish_commands (List[str]): commands to execute after backup is completed or failed

    """

    def __init__(
        self,
        cluster: cluster.Cluster,
        bucket: str = "",
        binary_path: str = "pg_dump",
        options: Optional[BackupOptions] = None,
        shell: Optional[_BaseShellEnv] = None,
    ):
        super().__init__(
            cluster=cluster, binary_path=binary_path, base_path=bucket, options=options, shell=shell
        )
        self.command = '{binary} {options} -d "{database}" | gsutil cp - "{path}"'


class FileRestore(_BackupRestoreOperation):
    """Restore class that performs a Restore operation from a local filesystem.
    Executes pg_restore on a target postgres cluster spawned as a subprocess of Postgres server process.

    Args:
        cluster (cluster.Cluster): Postgres cluster object
        base_path (str): Base backup path. If specified, the backup path would be considered relative to it.
        binary_path (str): Path to the pg_restore binary. Use when a specific binary version is needed or the binary is not in PATH.
        options (RestoreOptions): restore options represented by the RestoreOptions class
        shell (_BaseShellEnv): shell processor that defines pathing and escaping for the current environment

    Attributes:
        options (RestoreOptions): restore options represented by the RestoreOptions class
        cluster: Postgres cluster object
        binary: Path to the pg_restore binary
        on_start_commands (List[str]): commands to execute prior to launching the restore
        command (str): main restore command
        on_finish_commands (List[str]): commands to execute after restore is completed or failed


    Example:
        Restore objects into database bar changing object ownership to "bar"

        >>> old_db = "foo"  # doctest: +SKIP
        >>> new_db = "bar"  # doctest: +SKIP
        >>> role = "ownerrole"  # doctest: +SKIP
        >>> backup = FileBackup(cluster=cluster, base_path="/tmp")
        >>> backup.backup(database=old_db, path=f"{old_db}.bak")
        >>> restore = FileRestore(cluster=cluster, base_path="/tmp")
        >>> restore.options.schema_only = True
        >>> restore.options.no_owner = True
        >>> restore.options.tables = ["a", "b"]
        >>> restore.options.set_role = role
        >>> restore.restore(database=new_db, path=f"{old_db}.bak")
    """

    def __init__(
        self,
        cluster: cluster.Cluster,
        base_path: str = "",
        binary_path: str = "pg_restore",
        options: RestoreOptions = None,
        shell: Optional[_BaseShellEnv] = None,
    ):
        super().__init__(
            cluster=cluster,
            binary_path=binary_path,
            command='{binary} {options} -d "{database}" "{path}"',
            base_path=base_path,
            options=options if options else RestoreOptions(),
            shell=shell,
        )

    def restore(self, database: str, path: str):
        """Restore a backup into the specified database
        Args:
            database (str):    name of the database to connect to
            path (str):        path (relative or absolute) to the backup file

        Returns:
            str: pg_restore full output
        """
        return self.execute_command(database=database, path=path)


class GCPRestore(FileRestore):
    """GCP Restore class that manages restores from GCP buckets.
    Executes "pg_restore" on a target cluster spawned as a subprocess of Postgres server process.
    Requires "gsutil" command available on the server host.
    To configure authentication, run "gcloud auth login" under postgres OS user.
    GCP bucket file is first copied to temp_path, then restored from disk. The file is removed once restore is finished.

    Args:
        cluster (cluster.Cluster): Postgres cluster object
        bucket (str): (Optional) GCP bucket name to work with. If specified, the backup path would
            be considered relative of the bucket path
        binary_path (str): Path to the pg_restore binary. Use when a specific binary version is needed or the binary is not in PATH.
        temp_path (str): Path to a temporary folder, to which the backup would be copied to.
            Direct restores from the bucket via pipe has proven to be unreliable.

    Attributes:
        options (RestoreOptions): restore options represented by RestoreOptions class
        cluster: Postgres cluster to execute the restore
        binary: Path to the pg_restore binary.
        on_start_commands (List[str]): commands to execute prior to launching the restore
        command (str): main restore command
        on_finish_commands (List[str]): commands to execute after restore is completed or failed
        temp_path (str): Path to a temporary folder
    """

    def __init__(
        self,
        cluster: cluster.Cluster,
        bucket: str = "",
        binary_path: str = "pg_restore",
        temp_path: str = "/tmp",
        options: Optional[RestoreOptions] = None,
        shell: Optional[_BaseShellEnv] = None,
    ):
        super().__init__(
            cluster=cluster, binary_path=binary_path, base_path=bucket, options=options, shell=shell
        )
        self.temp_path = Path(temp_path)
        self.on_start_commands = [f'gsutil cp "{{path}}" "{self.temp_path}/{{filename}}"']
        self.on_finish_commands = [f'rm -f "{self.temp_path}/{{filename}}"']
        self.command = f'{{binary}} {{options}} -d "{{database}}" "{self.temp_path}/{{filename}}"'
