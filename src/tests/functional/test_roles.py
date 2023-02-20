from datetime import date, datetime
import re
import pytest

from pgmob import objects


@pytest.fixture
def tmp_role(test_role):
    """Creates a temporary user pgmobtest"""
    day = date.today()
    yield test_role.create(
        "pgmobtesttmp",
        params=(
            "PASSWORD 'foo' NOSUPERUSER INHERIT "
            "CREATEROLE NOCREATEDB NOREPLICATION LOGIN CONNECTION LIMIT 10 "
            f"VALID UNTIL '{str(day)}'"
        ),
    )


@pytest.fixture
def roles(cluster, tmp_role):
    yield objects.RoleCollection(cluster=cluster)


class TestFunctionalRoles:
    role_query = "SELECT {field} FROM pg_catalog.pg_roles" " WHERE rolname = '{role}'"

    def test_roles(self, roles: objects.RoleCollection, tmp_role: str):
        day = date.today()
        role_item = roles[tmp_role]
        assert role_item.name == tmp_role
        assert role_item.superuser == False
        assert role_item.inherit == True
        assert role_item.createrole == True
        assert role_item.createdb == False
        assert role_item.login == True
        assert role_item.replication == False
        assert role_item.connection_limit == 10
        assert role_item.bypassrls == False
        assert role_item.valid_until.date() == day
        assert role_item.oid > 0
        assert str(role_item) == f"Role('{tmp_role}')"

    # methods
    def test_get_password_md5(self, roles: objects.RoleCollection, tmp_role: str):
        role_item = roles[tmp_role]
        assert isinstance(role_item.get_password_md5(), str)
        assert re.search("^md5\\w{32}$", role_item.get_password_md5())

    def test_name(self, test_role, roles: objects.RoleCollection, psql, tmp_role):
        renamed = test_role.create("pgmobrenamerole")
        assert psql("DROP ROLE pgmobrenamerole").exit_code == 0
        role_obj = roles[tmp_role]
        role_obj.name = "tmpdoittwice"
        role_obj.name = renamed
        assert role_obj.name == renamed
        assert psql(self.role_query.format(field="rolname", role=tmp_role)).output == tmp_role
        role_obj.alter()
        assert psql(self.role_query.format(field="rolname", role=tmp_role)).output == ""
        assert role_obj.name == renamed
        roles.refresh()
        role_obj = roles[renamed]
        assert psql(self.role_query.format(field="rolname", role=renamed)).output == renamed

    def test_create(self, tmp_role, roles: objects.RoleCollection, psql):
        psql(f"DROP ROLE {tmp_role}")
        day = date.today()
        role_obj = roles.new(
            name=tmp_role, password="foobar", createdb=True, valid_until=day, connection_limit=2
        )
        role_obj.create()
        assert role_obj.oid > 0
        assert psql(self.role_query.format(field="rolname", role=tmp_role)).output == tmp_role
        assert psql(self.role_query.format(field="rolvaliduntil::date", role=tmp_role)).output == str(day)
        assert psql(self.role_query.format(field="rolcreatedb", role=tmp_role)).output == "t"
        assert psql(self.role_query.format(field="rolconnlimit", role=tmp_role)).output == "2"

    def test_script(self, tmp_role, roles: objects.RoleCollection, psql):
        role_obj = roles[tmp_role]
        assert re.match(
            "CREATE ROLE.*CREATEROLE.*LOGIN.*CONNECTION LIMIT.*VALID UNTIL", role_obj.script().decode("utf8")
        )

    def test_change_password(self, tmp_role: str, roles: objects.RoleCollection, psql):
        pw_query = f"SELECT rolpassword FROM pg_catalog.pg_authid WHERE rolname = '{tmp_role}'"
        old_pw = psql(pw_query).output
        roles[tmp_role].change_password("foobar")
        assert psql(pw_query).output != old_pw
