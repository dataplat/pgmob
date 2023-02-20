"""Postgresql roles"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Union
from ..adapters import AdapterError
from ..sql import SQL, Composable, Literal, Identifier
from ..errors import *
from .. import util
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class Role(generic._DynamicObject, generic._CollectionChild):
    """
    Postgres Role object. Represents a role object on a Postgres server.

    Args:
        name (str): name of the role
        password (str): role password with which it will be created
        cluster (str): Postgres cluster object
        superuser (bool): SUPERUSER permissions
        inherit (bool): INHERIT permissions
        createrole (bool): CREATEROLE permissions
        createdb (bool): CREATEDB permissions
        login (bool): LOGIN permissions
        replication (bool): REPLICATION permissions
        bypassrls (bool): BYPASSRLS enabled
        connection_limit (int): Role connection limit
        valid_until (datetime): Expires on this date
        oid (int): Role OID
        parent (DatabaseCollection): parent collection

    Attributes:
        name (str): Table name
        cluster (str): Postgres cluster object
        superuser (bool): SUPERUSER permissions
        inherit (bool): INHERIT permissions
        createrole (bool): CREATEROLE permissions
        createdb (bool): CREATEDB permissions
        login (bool): LOGIN permissions
        replication (bool): REPLICATION permissions
        bypassrls (bool): BYPASSRLS enabled
        connection_limit (int): Role connection limit
        valid_until (datetime): Expires on this date
        oid (int): Role OID
    """

    def __init__(
        self,
        name: str,
        password: str = None,
        cluster: "Cluster" = None,
        superuser: bool = False,
        inherit: bool = True,
        createrole: bool = False,
        createdb: bool = False,
        login: bool = False,
        replication: bool = False,
        bypassrls: bool = False,
        connection_limit: int = -1,
        valid_until: datetime = None,
        oid: int = None,
        parent: "RoleCollection" = None,
    ):
        super().__init__(kind="ROLE", cluster=cluster, oid=oid, name=name)
        generic._CollectionChild.__init__(self, parent=parent)
        self._password = password
        self._cluster = cluster
        self._superuser = superuser
        self._inherit = inherit
        self._createrole = createrole
        self._createdb = createdb
        self._login = login
        self._replication = replication
        self._bypassrls = bypassrls
        self._connection_limit = connection_limit
        self._valid_until = valid_until
        self._oid = oid

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        generic._set_ephemeral_attr(self, "name", name)

    @property
    def superuser(self) -> bool:
        return self._superuser

    @superuser.setter
    def superuser(self, value: bool):
        self._set_permission("superuser", value)

    @property
    def inherit(self) -> bool:
        return self._inherit

    @inherit.setter
    def inherit(self, value: bool):
        self._set_permission("inherit", value)

    @property
    def createrole(self) -> bool:
        return self._createrole

    @createrole.setter
    def createrole(self, value: bool):
        self._set_permission("createrole", value)

    @property
    def createdb(self) -> bool:
        return self._createdb

    @createdb.setter
    def createdb(self, value: bool):
        self._set_permission("createdb", value)

    @property
    def login(self) -> bool:
        return self._login

    @login.setter
    def login(self, value: bool):
        self._set_permission("login", value)

    @property
    def replication(self) -> bool:
        return self._replication

    @replication.setter
    def replication(self, value: bool):
        self._set_permission("replication", value)

    @property
    def bypassrls(self) -> bool:
        return self._bypassrls

    @bypassrls.setter
    def bypassrls(self, value: bool):
        self._set_permission("bypassrls", value)

    @property
    def valid_until(self) -> Optional[datetime]:
        return self._valid_until

    @valid_until.setter
    def valid_until(self, value: Optional[datetime]):
        self._set_attribute("valid_until", str(value))

    @property
    def connection_limit(self) -> int:
        return self._connection_limit

    @connection_limit.setter
    def connection_limit(self, value: Optional[int]):
        self._set_attribute("connection_limit", value)

    def _set_attribute(self, attr: str, value: Any):
        if getattr(self, f"_{attr}") != value:
            sql = SQL(f"ALTER ROLE {{fqn}} {attr.upper().replace('_', ' ')} {'%s' if value else 'DEFAULT'}")
            params = (value,) if value else None
            stmt = sql.format(fqn=self._sql_fqn())
            self._changes[attr] = generic._SQLChange(obj=self, sql=stmt, params=params)
            setattr(self, f"_{attr}", value)

    def _set_permission(self, attr: str, value: bool):
        if getattr(self, f"_{attr}") != value:
            permission = ("" if value else "NO") + attr.upper()
            stmt = SQL(f"ALTER ROLE {{fqn}} {permission}").format(fqn=self._sql_fqn())
            self._changes[attr] = generic._SQLChange(obj=self, sql=stmt)
            setattr(self, f"_{attr}", permission)

    def script(self, as_composable: bool = False) -> Union[str, Composable]:
        """Scripts out a role.

        Args:
            as_composable (bool): return Composable object instead of plain text

        Returns:
            Union[str, Composable]: role creation script
        """
        permission_list = {
            "SUPERUSER": self.superuser,
            "CREATEDB": self.createdb,
            "CREATEROLE": self.createrole,
            "INHERIT": self.inherit,
            "LOGIN": self.login,
            "REPLICATION": self.replication,
            "BYPASSRLS": self.bypassrls,
        }
        sql = "CREATE ROLE {role}"
        params: Dict[str, Composable] = {"role": self._sql_fqn()}
        password = self._password if self._password else self.get_password_md5()
        if password:
            sql += " PASSWORD {password}"
            params["password"] = Literal(password)
        for permission in permission_list.keys():
            sql += " " + (permission if permission_list[permission] else f"NO{permission}")
        if self.connection_limit is not None:
            sql += " CONNECTION LIMIT {limit}"
            params["limit"] = Literal(self.connection_limit)
        if self.valid_until is not None:
            sql += " VALID UNTIL {valid_until}"
            params["valid_until"] = Literal(str(self.valid_until))

        command = SQL(sql).format(**params)
        if as_composable:
            return command
        else:
            with self.cluster.adapter.cursor() as cur:
                return cur.mogrify(command)

    def create(self) -> None:
        """Create a role on the Postgres cluster"""
        self.cluster.execute(self.script(as_composable=True))
        sql = util.get_sql("get_role") + SQL(" WHERE rolname = %s")
        _RoleMapper(self.cluster.execute(sql, self.name)[0]).map(self)

    def drop(self, force: bool = False) -> None:
        """Drops the role connected to this object

        Args:
            force (bool): disallow new connections and terminate all existing ones for the role before executing the drop statement
        """
        if force:
            try:
                self.cluster.execute(SQL("ALTER ROLE {fqn} NOLOGIN").format(fqn=self._sql_fqn()))
                self.cluster.terminate(roles=[self.name])
            except AdapterError:
                if self.login:
                    self.cluster.execute(SQL("ALTER ROLE {fqn} LOGIN").format(fqn=self._sql_fqn()))
                raise
        self.cluster.execute(SQL("DROP ROLE {fqn}").format(fqn=self._sql_fqn()))

    def get_password_md5(self) -> Optional[str]:
        """Returns md5 password hash for the role"""
        sql = SQL("SELECT rolpassword FROM pg_catalog.pg_authid WHERE rolname = %s")
        result = self.cluster.execute(sql, self.name)
        if not result:
            raise PostgresError("Role %s is not found", self.name)
        return result[0][0]

    def refresh(self):
        """Re-initializes the object, refreshing its properties"""
        super().refresh()
        if not self._ephemeral:
            sql = util.get_sql("get_role") + SQL(" WHERE oid = %s")
            result = self.cluster.execute(sql, self._oid)
            if not result:
                raise PostgresError("Role not found")
            mapper = _RoleMapper(result[0])
            mapper.map(self)

    def change_password(self, password: str) -> None:
        """Changes the role's password

        Args:
            password (str): new password
        """
        sql = SQL("ALTER ROLE {role} PASSWORD {password}").format(
            role=Identifier(self.name), password=Literal(str(password))
        )
        self.cluster.execute(sql)


class _RoleMapper(generic._BaseObjectMapper[Role]):
    """Maps out a resultset from a database query to a role object"""

    attributes = [
        "name",
        "superuser",
        "inherit",
        "createrole",
        "createdb",
        "login",
        "replication",
        "connection_limit",
        "valid_until",
        "bypassrls",
        "oid",
    ]


class RoleCollection(generic._BaseCollection[Role]):
    """An iterable collection of roles indexed by role name.

    Args:
        cluster (str): Postgres cluster object

    Attributes:
        cluster (str): Postgres cluster object
    """

    def __init__(self, cluster):
        super().__init__(cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and retrieves objects from the cluster"""
        super().refresh()
        sql = util.get_sql("get_role") + SQL(" ORDER BY rolname")
        result = self.cluster.execute(sql)
        for mapper in [_RoleMapper(x) for x in result]:
            self[mapper["name"]] = mapper.map(Role(cluster=self.cluster, name=mapper["name"], parent=self))

    def new(
        self,
        name: str,
        password: str = None,
        superuser: bool = False,
        inherit: bool = True,
        createrole: bool = False,
        createdb: bool = False,
        login: bool = False,
        replication: bool = False,
        bypassrls: bool = False,
        connection_limit: int = -1,
        valid_until: datetime = None,
    ) -> Role:
        """Create a role object on the current Postgres cluster. The object
        is created ephemeral and either needs to be added to the role collection,
        or .create() needs to be executed.

        Args:
            name (str): name of the role
            password (str): role password with which it will be created
            superuser (bool): SUPERUSER permissions
            inherit (bool): INHERIT permissions
            createrole (bool): CREATEROLE permissions
            createdb (bool): CREATEDB permissions
            login (bool): LOGIN permissions
            replication (bool): REPLICATION permissions
            bypassrls (bool): BYPASSRLS enabled
            connection_limit (int): Role connection limit
            valid_until (datetime): Expires on this date
        """
        return Role(
            cluster=self.cluster,
            name=name,
            parent=self,
            password=password,
            superuser=superuser,
            inherit=inherit,
            createrole=createrole,
            createdb=createdb,
            login=login,
            replication=replication,
            bypassrls=bypassrls,
            connection_limit=connection_limit,
            valid_until=valid_until,
        )

    def add(self, role: Role):
        """Adds the role object to the collection, simultaneously creating it on the cluster

        Args:
            role (Role): initialized role object
        """
        role.cluster = self.cluster
        role._parent = self
        role.create()
        self[role.name] = role
