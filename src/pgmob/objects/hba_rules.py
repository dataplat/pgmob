"""HBA rules as collection of strings that ignore whitespace on comparison"""
import collections
import re
from typing import Any, Iterable, List, Optional, Tuple, Union, TYPE_CHECKING

from ..adapters import ProgrammingError
from ..sql import SQL, Literal
from ..adapters.base import BaseCursor
from ..errors import *
from . import generic


if TYPE_CHECKING:
    from ..cluster import Cluster


class HBARule(str):
    """A record in pg_hba.conf file.
    Whitespace is considered equal upon object comparison.

    Args:
        str: A line from pg_hba.conf file
    """

    def __eq__(self, other):
        left = self.split()
        right = str(other).split()
        return left == right

    def __ne__(self, other):
        return not self.__eq__(other)

    def _get_field(self, name: str) -> Optional[str]:
        fields = self.fields
        field_map = {}
        auth_options: List[str] = []
        for i in range(len(fields)):
            if fields[i].startswith("#"):
                # anything after is a comment
                break
            if i == 0:
                field_map["type"] = fields[i]
                continue
            if i == 1:
                field_map["database"] = fields[i]
                continue
            if i == 2:
                field_map["user"] = fields[i]
                continue
            if i == 3:
                if field_map["type"] == "local":
                    field_map["auth_method"] = fields[i]
                else:
                    field_map["address"] = fields[i]
                continue
            if i == 4:
                if field_map["type"] == "local":
                    auth_options.append(fields[i])
                elif re.match("\\d{1,3}\.\\d{1,3}\.\\d{1,3}\\.\\d{1,3}", fields[i]):
                    field_map["mask"] = fields[i]
                else:
                    field_map["auth_method"] = fields[i]
                continue
            if i == 5:
                if field_map["type"] == "local":
                    auth_options.append(fields[i])
                elif "mask" in field_map:
                    field_map["auth_method"] = fields[i]
                else:
                    auth_options.append(fields[i])
                continue
            if i > 5:
                auth_options.append(fields[i])
        if name == "auth_options":
            return " ".join(auth_options)
        else:
            return field_map.get(name, None)

    @property
    def fields(self) -> List[str]:
        """A tuple of pg_hba.conf fields extracted from the record"""
        return self.split()

    @property
    def type(self) -> Optional[str]:
        """The type field"""
        return self._get_field("type")

    @property
    def database(self) -> Optional[str]:
        """The database field"""
        return self._get_field("database")

    @property
    def user(self) -> Optional[str]:
        """The user field"""
        return self._get_field("user")

    @property
    def address(self) -> Optional[str]:
        """The address field"""
        return self._get_field("address")

    @property
    def mask(self) -> Optional[str]:
        return self._get_field("mask")

    @property
    def auth_method(self) -> Optional[str]:
        return self._get_field("auth_method")

    @property
    def auth_options(self) -> Optional[str]:
        return self._get_field("auth_options")


class HBARuleCollection(collections.UserList[HBARule], generic._ClusterBound):
    """A collection of HBA rules in pg_hba.conf file

    Args:
        list: A list of lines from pg_hba or HBARule objects
        cluster (str): Postgres cluster object

    Attributes:
        cluster (str): Postgres cluster object
    """

    def __init__(self, cluster: "Cluster"):
        collections.UserList.__init__(self, [])
        generic._ClusterBound.__init__(self, cluster=cluster)
        if cluster:
            self.refresh()

    def refresh(self):
        """Resets any pending changes and retrieves objects from the cluster"""

        self.clear()

        def task(cursor: BaseCursor):
            cursor.execute(
                SQL(
                    """
                CREATE TEMPORARY TABLE pg_hba(
                id int GENERATED ALWAYS AS IDENTITY,
                lines text
            );
            """
                )
            )
            try:
                hba_file = cursor.scalar(
                    SQL("SELECT setting FROM pg_settings WHERE name = %s"), ("hba_file",)
                )
                cursor.execute(SQL("COPY pg_hba(lines) FROM %s"), (hba_file,))
                cursor.execute(SQL("SELECT lines FROM pg_hba ORDER BY id"))
                lines = cursor.fetchall()
            except ProgrammingError as e:
                raise PostgresError(e)
            finally:
                cursor.execute(SQL("DROP TABLE pg_hba;"))
            return [x[0] for x in lines]

        lines = self.cluster.execute_with_cursor(task)
        self.data.extend([HBARule(x) for x in lines])

    def __contains__(self, o: object) -> bool:
        return HBARule(o) in self.data

    def __iadd__(self, other: Iterable[HBARule]):
        self.data.extend([HBARule(r) for r in other])
        return self

    def __add__(self, other: Iterable[HBARule]):
        self.data.extend([HBARule(r) for r in other])
        return self

    def extend(self, item: Iterable[HBARule]):
        """Add multiple HBA rules to the collection

        Args:
            item(Iterable[Any]): An iterable of lines from pg_hba as strings or HBARule object
        """
        self.data.extend([HBARule(x) for x in item])

    def append(self, item: Union[str, HBARule]):
        """Append an HBA rule to the collection

        Args:
            item(Union[str, HBARule]): A line from pg_hba or HBARule object
        """
        self.data.append(HBARule(item))

    def remove(self, item: Union[str, HBARule]):
        """Remove an HBA rule from the collection

        Args:
            item(Union[str, HBARule]): A line from pg_hba or HBARule object
        """
        self.data.remove(HBARule(item))

    def index(self, item: Union[str, HBARule], *args) -> int:
        """Return a first index of a matching HBA rule from the collection

        Args:
            item(Union[str, HBARule]): A line from pg_hba or HBARule object
        """
        return self.data.index(HBARule(item), *args)

    def insert(self, index: int, item: Union[str, HBARule]):
        """Insert an HBA rule into the rule collection with a certain index

        Args:
            item(Union[str, HBARule]): A line from pg_hba or HBARule object
            index(int): Position to use
        """
        self.data.insert(index, HBARule(item))

    def alter(self):
        """Write HBA collection back into pg_hba.conf on the Postgres server."""

        def task(cursor):
            cursor.execute(
                SQL(
                    """CREATE TEMPORARY TABLE pg_hba(
                        id int GENERATED ALWAYS AS IDENTITY,
                        lines text
                    )"""
                )
            )
            try:
                hba_file = cursor.scalar(
                    SQL("SELECT setting FROM pg_settings WHERE name = %s"), ("hba_file",)
                )
                # load current lines and make a copy
                cursor.execute(SQL("COPY pg_hba(lines) FROM %s"), (hba_file,))
                cursor.execute(
                    SQL("COPY (SELECT lines FROM pg_hba ORDER BY id) TO %s"), (f"{hba_file}.bak.pgm",)
                )
                cursor.execute(SQL("DELETE FROM pg_hba"))
                # upload new rules and write them to the file
                cursor.execute(
                    SQL("INSERT INTO pg_hba(lines) VALUES {values}").format(
                        values=SQL(", ").join([SQL("({value})").format(value=Literal(x)) for x in self])
                    )
                )
                cursor.execute(SQL("COPY (SELECT lines FROM pg_hba ORDER BY id) TO %s"), (hba_file,))
            except ProgrammingError as e:
                raise PostgresError(e)
            finally:
                cursor.execute(SQL("DROP TABLE pg_hba"))

        self.cluster.execute_with_cursor(task)
