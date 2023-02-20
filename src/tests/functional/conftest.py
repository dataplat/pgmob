from typing import Callable
from types import ModuleType
from dataclasses import dataclass
import pytest
import docker
import os
import time
from docker.types import ContainerSpec
from pgmob.cluster import Cluster


def pytest_runtest_setup(item):
    """Skip tests if instance details are not defined"""
    try:
        docker.from_env()
    except docker.errors.DockerException:
        pytest.skip("Functional tests disabled, docker service not found")


@pytest.fixture(scope="session")
def docker_client() -> docker.DockerClient:
    """Returns an initialized docker client"""
    return docker.from_env()


@pytest.fixture(scope="session")
def hostname() -> str:
    """Returns docker container hostname to use for connection"""
    return os.environ.get("PGMOB_HOST", "localhost")


@pytest.fixture(scope="session")
def container_name() -> str:
    """Returns docker container name"""
    return os.environ.get("PGMOB_CONTAINER_NAME", "pgmob-postgres")


@pytest.fixture(scope="session")
def pg_password() -> str:
    """Returns postgres password"""
    return os.environ.get("PGMOB_PASSWORD", "Qwert123!")


@pytest.fixture(scope="session")
def container(docker_client: docker.DockerClient, container_name, pg_password):
    pg_image = os.environ.get("PGMOB_IMAGE", "postgres:12")
    container_network = os.environ.get("PGMOB_CONTAINER_NETWORK", "bridge")
    image_env = {
        "POSTGRES_PASSWORD": pg_password,
    }
    ports = {"5432/tcp": 5432}
    command = "postgres -c 'wal_level=logical'"
    if not docker_client.images.list(pg_image):
        docker_client.images.pull(pg_image)
    try:
        container = docker_client.containers.get(container_name)
        if container.status == "running":
            container.stop()
        container.remove()
    except docker.errors.NotFound:
        pass
    container = docker_client.containers.create(
        image=pg_image,
        environment=image_env,
        ports=ports,
        command=command,
        name=container_name,
        network=container_network,
    )
    container.start()
    # wait until pg is ready
    attempts = 0
    while attempts < 30:
        if container.exec_run("pg_isready").exit_code == 0:
            if container.exec_run('psql -U postgres -c "select 1"').exit_code == 0:
                break
        attempts += 1
        time.sleep(1)

    yield container
    # teardown

    container.stop()
    container.remove()
    # self.docker_client.containers.prune()
    docker_client.close()


@pytest.fixture
def test_db(psql, container):
    """Creates a temporary DB in a container

    Args:
        name (str) - database name
    """

    class TestDb:
        dbs = set()

        @staticmethod
        def create(name):
            TestDb.dbs.add(name)
            assert psql(f"CREATE DATABASE {name} TEMPLATE template0").exit_code == 0
            return name

        @staticmethod
        def create_with_table(name):
            TestDb.create(name)
            assert psql(cmd="CREATE TABLE test(a int)", db=name).exit_code == 0
            return name

    yield TestDb

    for db in TestDb.dbs:
        assert (
            psql(f"select pg_terminate_backend(pid) from pg_stat_activity where datname = '{db}'").exit_code
            == 0
        )
        assert container.exec_run(f"dropdb -U postgres --if-exists {db}").exit_code == 0


@pytest.fixture
def psql(container: ContainerSpec):
    """Callable that runs a command locally in postgresql container using psql binary.

    Args:
        cmd (str) - sql command
        db (str) - database name. "postgres" by default
    """

    @dataclass
    class ExecRunOutput:
        output: str
        exit_code: int

    def wrapper(cmd, db="postgres"):
        result = container.exec_run(
            ["sh", "-c", f'psql -twA -v "ON_ERROR_STOP=1" -U postgres -d "{db}" << EOM\n{cmd}\nEOM\n']
        )
        return ExecRunOutput(output=result.output.decode("utf8").strip(), exit_code=result.exit_code)

    return wrapper


@pytest.fixture
def db(test_db):
    """Creates database pgmobtest and cleans it up afterwards"""
    yield test_db.create("pgmobtest")


@pytest.fixture
def old_db(db):
    """Creates database pgmobtest and cleans it up afterwards"""
    yield db


@pytest.fixture
def new_db(test_db):
    """Creates database pgmobtest2 and cleans it up afterwards"""
    yield test_db.create("pgmobtest2")


@pytest.fixture
def db_with_table(test_db):
    """Creates database pgmobtest with a table in it and cleans it up afterwards"""
    yield test_db.create_with_table("pgmobtest")


@pytest.fixture
def test_role(psql, container):
    """Creates a temporary user

    Args:
        name (str) - user name
    """

    class TestRole:
        roles = set()

        @staticmethod
        def create(name, params=""):
            TestRole.roles.add(name)
            assert psql(f"CREATE USER {name} {params}").exit_code == 0
            return name

    yield TestRole

    for role in TestRole.roles:
        assert container.exec_run(f"dropuser -U postgres --if-exists {role}").exit_code == 0


@pytest.fixture
def role(test_role):
    """Creates a temporary user pgmobtest"""
    yield test_role.create("pgmobtest")


@pytest.fixture
def schema(psql, db):
    """Creates a temporary schema tmp in database pgmobtest"""
    schema = "tmp"
    assert psql(f"CREATE SCHEMA {schema}", db=db).exit_code == 0
    yield schema


@pytest.fixture
def tablespace(psql, container):
    """Creates a temporary tablespace"""
    tablespace = "pgmobtblspc"
    assert container.exec_run(f"su - postgres -c 'mkdir -p /tmp/{tablespace}'").exit_code == 0
    assert psql(f"CREATE TABLESPACE {tablespace} LOCATION '/tmp/{tablespace}'").exit_code == 0
    yield tablespace
    assert psql(f"DROP TABLESPACE {tablespace}").exit_code == 0


@pytest.fixture
def connect(container, container_name, pg_password):
    """Cluster object factory.

    Args:
        dbname (str) - database name. "postgres" by default
    """

    def wrapper(db=None, adapter=None):
        from pgmob.adapters import psycopg2 as _psycopg2

        if not adapter:
            adapter = _psycopg2.Psycopg2Adapter(cursor_factory=None)
        return Cluster(
            host=container_name,
            port=5432,
            user="postgres",
            password=pg_password,
            dbname=db,
            adapter=adapter,
        )

    return wrapper


@pytest.fixture
def cluster(connect):
    """Creates a Cluster object connected to the postgres database"""
    yield connect()


@pytest.fixture
def cluster_db(connect, db):
    """Creates a Cluster object connected to the pgmobtest database"""
    yield connect(db=db)


@pytest.fixture
def plugin():
    """Replication slot plugin name"""
    return "test_decoding"


@pytest.fixture
def replication_slot(psql, plugin, db):
    """Creates a temporary replication slot"""
    slot = "test_slot"
    psql(f"SELECT pg_create_logical_replication_slot('{slot}', '{plugin}')", db=db)
    yield slot
    psql(f"SELECT pg_drop_replication_slot('{slot}')", db=db)


@pytest.fixture
def lo_ids_factory(psql, container):
    """Creates a set of large objects factory"""

    def wrapper(db="postgres"):
        container.exec_run(["sh", "-c", "echo foobar > /tmp/foo.lo"])
        container.exec_run(["sh", "-c", "echo zoobar > /tmp/zoo.lo"])
        los = []
        for file in ["foo", "zoo"]:
            los.append(int(psql(f"\lo_import /tmp/{file}.lo", db=db).output.split(" ")[1]))

        return los

    return wrapper


@pytest.fixture
def lo_ids(lo_ids_factory):
    """Creates a set of large objects"""
    return lo_ids_factory()


@pytest.fixture
def doctest_globs_factory(cluster, role, db, old_db, new_db, schema) -> Callable[[ModuleType], dict]:
    """Generates global variables for the doctest module tests"""

    def wrapper(m: ModuleType) -> dict:
        globs = m.__dict__.copy()
        globs.update(
            {"cluster": cluster, "db": db, "role": role, "old_db": old_db, "new_db": new_db, "schema": schema}
        )
        return globs

    return wrapper
