from unittest.mock import call

from pgmob.backup import BackupOptions, FileBackup, FileRestore, GCPBackup, GCPRestore, RestoreOptions


class TestBackup:
    def test_backup_conflict(self, cluster):
        backup = FileBackup(cluster=cluster)
        backup2 = FileBackup(cluster=cluster)
        backup2.options.clean = True
        assert backup.options.render_args() != backup2.options.render_args()
        assert backup.options != backup2.options

        backup.backup(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(command=('pg_dump --format=c -d "foo" > "/tmp/foo"'))

    def test_backup_init(self, cluster):
        backup = FileBackup(cluster=cluster)
        options = backup.options
        assert isinstance(options, BackupOptions)

        # shared
        assert options.data_only == False
        assert options.schema_only == False
        assert options.strict_names == False
        assert options.add_if_exists == False
        assert options.no_privileges == False
        assert options.no_subscriptions == False
        assert options.no_publications == False
        assert options.no_tablespaces == False
        assert options.clean == False
        assert options.create == False
        assert options.verbose == False

        assert options.superuser == None
        assert options.set_role == None
        assert options.section == None

        assert options.tables == []
        assert options.schemas == []
        assert options.exclude_schemas == []
        assert options.format == "c"

        # backup only
        assert options.compress == False
        assert options.as_inserts == False
        assert options.create_database == False

        assert options.lock_wait_timeout == None

        assert options.compression_level == 5
        assert options.exclude_tables == []
        assert options.exclude_table_data == []

    def test_backup_options_render_args(self):
        options = BackupOptions()
        options.schema_only = True
        options.compress = True
        options.tables = ["a", "b"]
        options.set_role = "mahrole"
        options.exclude_table_data = ["a"]
        options.blobs = False

        result = options.render_args()
        assert "--schema-only" in result
        assert "--compress=5" in result
        assert '--table="a"' in result
        assert '--table="b"' in result
        assert '--role="mahrole"' in result
        assert '--exclude-table-data="a"' in result
        assert "--no-blobs" in result

    def test_file_backup_absolute(self, cluster):
        backup = FileBackup(cluster=cluster)
        backup.backup(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(command='pg_dump --format=c -d "foo" > "/tmp/foo"')

    def test_file_backup_binary(self, cluster):
        backup = FileBackup(cluster=cluster, binary_path="foobar")
        backup.backup(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(command='foobar --format=c -d "foo" > "/tmp/foo"')

    def test_file_backup_relative(self, cluster):
        backup = FileBackup(cluster=cluster, base_path="/tmp")
        backup.backup(database="foo", path="bar")
        cluster.run_os_command.assert_called_with(command='pg_dump --format=c -d "foo" > "/tmp/bar"')

    def test_file_backup_shared_params(self, cluster):
        backup = FileBackup(cluster=cluster)
        backup.options.schema_only = True
        backup.options.tables = ["a", "b"]
        backup.options.set_role = "mahrole"
        backup.backup(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(
            command=(
                'pg_dump --schema-only --table="a" --table="b" --format=c'
                ' --role="mahrole" -d "foo" > "/tmp/foo"'
            )
        )

    def test_file_backup_params(self, cluster):
        backup = FileBackup(cluster=cluster)
        backup.options.compress = True
        backup.options.exclude_table_data = ["a"]
        backup.options.blobs = False

        backup.backup(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(
            command=(
                'pg_dump --format=c --compress=5 --no-blobs --exclude-table-data="a" -d "foo" > "/tmp/foo"'
            )
        )

    def test_gcp_backup_absolute(self, cluster):
        backup = GCPBackup(cluster=cluster)
        backup.backup(database="foo", path="gs://tmp/foo")
        cluster.run_os_command.assert_called_with(
            command='pg_dump --format=c -d "foo" | gsutil cp - "gs://tmp/foo"'
        )

    def test_gcp_backup_bucket(self, cluster):
        backup = GCPBackup(cluster=cluster, bucket="gs://tmp/")
        backup.backup(database="foo", path="bar")
        cluster.run_os_command.assert_called_with(
            command='pg_dump --format=c -d "foo" | gsutil cp - "gs://tmp/bar"'
        )

    def test_gcp_backup_shared_params(self, cluster):
        backup = GCPBackup(cluster=cluster)
        backup.options.schema_only = True
        backup.options.tables = ["a", "b"]
        backup.options.set_role = "mahrole"
        backup.backup(database="foo", path="gs://tmp/foo")
        cluster.run_os_command.assert_called_with(
            command=(
                'pg_dump --schema-only --table="a" --table="b" --format=c'
                ' --role="mahrole" -d "foo" | gsutil cp - "gs://tmp/foo"'
            )
        )

    def test_gcp_backup_paramrs(self, cluster):
        backup = GCPBackup(cluster=cluster)
        backup.options.compress = True
        backup.options.exclude_table_data = ["a"]

        backup.backup(database="foo", path="gs://tmp/foo")
        cluster.run_os_command.assert_called_with(
            command=(
                'pg_dump --format=c --compress=5 --exclude-table-data="a" -d "foo" | gsutil cp - "gs://tmp/foo"'
            )
        )


class TestRestore:
    def test_restore_init(self, cluster):
        restore = FileRestore(cluster=cluster)
        options = restore.options
        assert options.__class__ is RestoreOptions

        # shared
        assert options.data_only == False
        assert options.schema_only == False
        assert options.strict_names == False
        assert options.add_if_exists == False
        assert options.no_privileges == False
        assert options.no_subscriptions == False
        assert options.no_publications == False
        assert options.no_tablespaces == False
        assert options.clean == False
        assert options.create == False
        assert options.verbose == False

        assert options.superuser == None
        assert options.set_role == None
        assert options.section == None
        assert options.format == None

        assert options.tables == []
        assert options.schemas == []
        assert options.exclude_schemas == []

        # restore only
        assert options.exit_on_error == False
        assert options.single_transaction == False
        assert options.disable_triggers == False
        assert options.no_data_for_failed_tables == False

        assert options.jobs == None
        assert options.use_list == None

        assert options.functions == []
        assert options.indexes == []
        assert options.triggers == []

    def test_restore_options_render_args(self):
        options = RestoreOptions()
        options.schema_only = True
        options.jobs = 4
        options.tables = ["a", "b"]
        options.set_role = "mahrole"
        options.indexes = ["a"]

        result = options.render_args()
        assert "--schema-only" in result
        assert "--jobs=4" in result
        assert '--table="a"' in result
        assert '--table="b"' in result
        assert '--index="a"' in result
        assert '--role="mahrole"' in result

    def test_file_restore_absolute(self, cluster):
        restore = FileRestore(cluster=cluster)
        restore.restore(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(command='pg_restore  -d "foo" "/tmp/foo"')

    def test_file_restore_binary(self, cluster):
        restore = FileRestore(cluster=cluster, binary_path="foobar")
        restore.restore(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(command='foobar  -d "foo" "/tmp/foo"')

    def test_file_restore_relative(self, cluster):
        restore = FileRestore(cluster=cluster, base_path="/tmp")
        restore.restore(database="foo", path="bar")
        cluster.run_os_command.assert_called_with(command='pg_restore  -d "foo" "/tmp/bar"')

    def test_file_restore_shared_params(self, cluster):
        restore = FileRestore(cluster=cluster)
        restore.options.schema_only = True
        restore.options.tables = ["a", "b"]
        restore.options.set_role = "mahrole"
        restore.restore(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(
            command=('pg_restore --schema-only --table="a" --table="b" --role="mahrole" -d "foo" "/tmp/foo"')
        )

    def test_file_restore_params(self, cluster):
        restore = FileRestore(cluster=cluster)
        restore.options.disable_triggers = True
        restore.options.indexes = ["a", "b"]
        restore.options.jobs = 4

        restore.restore(database="foo", path="/tmp/foo")
        cluster.run_os_command.assert_called_with(
            command=('pg_restore --index="a" --index="b" --jobs=4 --disable-triggers -d "foo" "/tmp/foo"')
        )

    def test_gcp_restore_absolute(self, cluster):
        restore = GCPRestore(cluster=cluster)
        restore.restore(database="foo", path="gs://tmp/foo")
        cluster.run_os_command.assert_has_calls(
            [
                call(command='gsutil cp "gs://tmp/foo" "/tmp/foo"'),
                call(command='pg_restore  -d "foo" "/tmp/foo"'),
                call(command='rm -f "/tmp/foo"'),
            ]
        )

    def test_gcp_restore_bucket(self, cluster):
        restore = GCPRestore(cluster=cluster, bucket="gs://tmp/")
        restore.restore(database="foo", path="bar")
        cluster.run_os_command.assert_has_calls(
            [
                call(command='gsutil cp "gs://tmp/bar" "/tmp/bar"'),
                call(command='pg_restore  -d "foo" "/tmp/bar"'),
                call(command='rm -f "/tmp/bar"'),
            ]
        )

    def test_gcp_restore_shared_params(self, cluster):
        restore = GCPRestore(cluster=cluster)
        restore.options.schema_only = True
        restore.options.tables = ["a", "b"]
        restore.options.set_role = "mahrole"
        restore.restore(database="foo", path="gs://tmp/foo")
        cluster.run_os_command.assert_has_calls(
            [
                call(command='gsutil cp "gs://tmp/foo" "/tmp/foo"'),
                call(
                    command=(
                        'pg_restore --schema-only --table="a" --table="b"'
                        ' --role="mahrole" -d "foo" "/tmp/foo"'
                    )
                ),
                call(command='rm -f "/tmp/foo"'),
            ]
        )

    def test_gcp_restore_params(self, cluster):
        restore = GCPRestore(cluster=cluster)
        restore.options.disable_triggers = True
        restore.options.indexes = ["a", "b"]
        restore.options.jobs = 4
        restore.restore(database="foo", path="gs://tmp/foo")
        cluster.run_os_command.assert_has_calls(
            [
                call(command='gsutil cp "gs://tmp/foo" "/tmp/foo"'),
                call(
                    command='pg_restore --index="a" --index="b" --jobs=4 --disable-triggers -d "foo" "/tmp/foo"'
                ),
                call(command='rm -f "/tmp/foo"'),
            ]
        )
