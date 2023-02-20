import pytest
import doctest
from pgmob.backup import FileBackup, FileRestore
from pgmob.errors import PostgresShellCommandError


def cleanup_file(container, file):
    container.exec_run(f"rm -f '{file}'")


@pytest.fixture
def backup(container):
    class TestBackup:
        files = []

        @staticmethod
        def dump(db, path):
            TestBackup.files.append(path)
            assert container.exec_run(f"pg_dump -U postgres -d '{db}' -Fc -f '{path}'").exit_code == 0
            return path

    yield TestBackup

    for file in TestBackup.files:
        container.exec_run(f"rm -f '{file}'")


class TestBackupFile:
    def test_file_base_path_backup(self, connect, db_with_table, container):
        path = "/tmp/" + db_with_table
        cluster = connect()
        cleanup_file(container, path)
        backup = FileBackup(cluster=cluster, base_path="/tmp")
        backup.backup(database=db_with_table, path=db_with_table)
        assert cluster.run_os_command(f"ls {path}").text == path
        cleanup_file(container, path)

    def test_nonexistent_base_path_backup(self, connect, db_with_table):
        path = "/nonexistingpath/" + db_with_table
        cluster = connect()
        backup = FileBackup(cluster=cluster, base_path="/nonexistingpath/")
        pytest.raises(
            PostgresShellCommandError,
            backup.backup,
            database=db_with_table,
            path=db_with_table,
        )

    def test_file_absolute_backup(self, connect, db_with_table, container):
        path = "/tmp/" + db_with_table
        cluster = connect()
        cleanup_file(container, path)
        backup = FileBackup(cluster=cluster)
        backup.backup(database=db_with_table, path=path)
        assert cluster.run_os_command(f"ls {path}").text == path
        cleanup_file(container, path)

    def test_nonexistent_absolute_backup(self, connect, db_with_table):
        path = "/nonexistingpath/" + db_with_table
        cluster = connect()
        backup = FileBackup(cluster=cluster)
        pytest.raises(
            PostgresShellCommandError,
            backup.backup,
            database=db_with_table,
            path=path,
        )


class TestRestoreFile:
    def test_nonexistent_restore(self, connect, new_db):
        cluster = connect()
        restore = FileRestore(cluster=cluster, base_path="/tmp")
        pytest.raises(
            PostgresShellCommandError,
            restore.restore,
            database=new_db,
            path="foo",
        )

    def test_nonexistent_absolute_restore(self, connect, new_db):
        cluster = connect()
        restore = FileRestore(cluster=cluster)
        pytest.raises(
            PostgresShellCommandError,
            restore.restore,
            database=new_db,
            path="/tmp/foo",
        )

    def test_file_base_path_restore(self, connect, db_with_table, backup, new_db, container):
        path = "/tmp/" + db_with_table
        backup.dump(db_with_table, path)
        cluster = connect()
        restore = FileRestore(cluster=cluster, base_path="/tmp")
        restore.restore(database=new_db, path=db_with_table)
        db = connect(db=new_db)
        assert "test" in db.tables
        cleanup_file(container, path)


def test_doctest(doctest_globs_factory):
    from pgmob import backup as backup_module

    results = doctest.testmod(m=backup_module, globs=doctest_globs_factory(backup_module))
    assert results.failed == 0
