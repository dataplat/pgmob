from typing import Any, Callable, Optional, Sequence, Union
import psycopg2  # type: ignore
import psycopg2.sql  # type: ignore
import psycopg2.extras  # type: ignore
import psycopg2.extensions  # type: ignore
from . import ProgrammingError, AdapterError, NoResultsToFetch
from ..sql import SQL, Identifier, Literal, Composable
from .base import BaseAdapter, BaseCursor, BaseLargeObject


class Psycopg2Cursor(BaseCursor):
    """Psycopg2 Cursor Adapter. Defines the cursor behaviour when working with psycopg2 module.

    Args:
        connection (Any): psycopg2 connection object
        *args, **kwargs: any other parameters to be passed on to the cursor
    """

    def __init__(self, connection: Any, *args, **kwargs) -> None:
        self.cursor = connection.cursor(*args, **kwargs)

    @property
    def statusmessage(self) -> str:
        """Cursor status message"""
        return self.cursor.statusmessage

    @property
    def closed(self) -> bool:
        """Specifies if the cursor is closed"""
        return self.cursor.closed

    @property
    def rowcount(self) -> int:
        """Row count of the most recent execute"""
        return self.cursor.rowcount

    def _convert_query(self, query: Union[Composable, str]) -> Union[psycopg2.sql.Composable, str]:
        conv_map = {SQL: psycopg2.sql.SQL, Literal: psycopg2.sql.Literal, Identifier: psycopg2.sql.Identifier}
        if isinstance(query, Composable):
            return psycopg2.sql.Composed([conv_map[part.__class__](part.value()) for part in query.compose()])
        else:
            return query

    def _try_exec(self, func: Callable) -> Any:
        try:
            return func()
        except psycopg2.ProgrammingError as e:
            if str(e) == "no results to fetch":
                raise NoResultsToFetch("No results to fetch") from e
            else:
                raise ProgrammingError("Adapter reported a programming error") from e
        except psycopg2.Error as e:
            raise AdapterError("Adapter reported an error") from e

    def close(self) -> None:
        """Close the currently open cursor"""
        return self.cursor.close()

    def execute(self, query: Union[Composable, str], params: tuple = None) -> None:
        """Execute a query with parameters

        Args:
            query (Union[Composable, str]): query object or string
            params (tuple): query parameters as a tuple

        """
        self._try_exec(lambda: self.cursor.execute(self._convert_query(query), params))

    def executemany(self, query: Union[Composable, str], params: Sequence[tuple] = None) -> None:
        """Execute a query with multiple parameter sets"""
        self._try_exec(lambda: self.cursor.executemany(self._convert_query(query), params))

    def mogrify(self, query: Union[Composable, str], params: tuple = None) -> bytes:
        """Returns a parsed SQL query based on the parameters provided

        Returns:
            bytes: a bytes query string
        """
        return self._try_exec(lambda: self.cursor.mogrify(self._convert_query(query), params))

    def fetchall(self) -> list:
        """Fetch all rows

        Returns:
            list: a ResultSet with the with the query results, if any.
        """
        return self._try_exec(lambda: self.cursor.fetchall())

    def fetchone(self) -> Any:
        """Fetch one row

        Returns:
            Any: a single row of the ResultSet"""
        return self._try_exec(lambda: self.cursor.fetchone())


class Psycopg2LargeObject(BaseLargeObject):
    """Large Object adapter. Implements Large Object interactions when working with psycopg2 module.

    Args:
        connection (Any): connection object
        oid (int): large object oid
        mode (str): connection mode:
            - r  Open for read only
            - w  Open for write only
            - rw Open for read/write
            - n  Don’t open the file
            - b  Return data as bytes
            - t  Decode data as string
    """

    def __init__(self, connection: Any, oid: int, mode: str, *args, **kwargs) -> None:
        self.lobject = connection.lobject(oid, mode=mode, *args, **kwargs)

    @property
    def closed(self) -> bool:
        """Specifies if the large object is closed"""
        return self.lobject.closed

    def close(self):
        """Close and deallocate large object"""
        self.lobject.close()

    def truncate(self, length: int = 0):
        """Truncate large object

        Args:
            length (int): size to truncate. 0 to remove
        """
        self.lobject.truncate(length)

    def write(self, data: bytes) -> int:
        """Write large object

        Returns:
            int: number of bytes written"""
        return self.lobject.write(data)

    def read(self) -> Union[str, bytes]:
        """Read large object

        Returns:
            Union[str, bytes]: string or bytes depending on the large object open mode
        """
        return self.lobject.read()

    def unlink(self):
        """Remove large object"""
        self.lobject.unlink()

    def __del__(self):
        if not self.lobject.closed:
            self.lobject.close()


class Psycopg2Adapter(BaseAdapter):
    """Psycopg2 adapter for PGMob. Implements all necessary protocols to communicate with
    Postgres using psycopg2 module."""

    def __init__(
        self,
        cursor_factory: Optional[psycopg2.extras.DictCursorBase] = None,
    ) -> None:
        self._cursor_factory = cursor_factory
        self.connection: Any = None

    def connect(self, *args, **kwargs) -> Any:
        """Establish connection to the Postgres server."""
        self.connection = psycopg2.connect(*args, **kwargs)

    def cursor(self) -> Psycopg2Cursor:
        """Retrieve the cursor object using the current connection"""
        return Psycopg2Cursor(connection=self.connection, cursor_factory=self._cursor_factory)

    def lobject(self, oid: int, mode: str) -> Psycopg2LargeObject:
        """Retrieve the large object handler using the current connection

        Args:
            oid (int): large object oid
            mode (str): connection mode:
                - r  Open for read only
                - w  Open for write only
                - rw Open for read/write
                - n  Don’t open the file
                - b  Return data as bytes
                - t  Decode data as string
        """
        return Psycopg2LargeObject(connection=self.connection, oid=oid, mode=mode)

    @property
    def is_connected(self) -> bool:
        """Defines whether the connection is open or closed"""
        return bool(self.connection) and not bool(self.connection.closed)

    @property
    def is_in_transaction(self) -> bool:
        """Defines whether the transaction is currently open"""
        return self.connection.status == psycopg2.extensions.STATUS_IN_TRANSACTION

    def commit(self) -> None:
        """Commit the open transaction"""
        self.connection.commit()

    def rollback(self) -> None:
        """Rollback the open transaction"""
        self.connection.rollback()

    def close_connection(self) -> None:
        """Close the connection immediately. The connection will be unusable from this point forward."""
        self.connection.close()

    def get_autocommit(self) -> bool:
        """Get autocommit status"""
        return self.connection.autocommit

    def set_autocommit(self, state: bool) -> None:
        """Set autocommit status"""
        self.connection.autocommit = bool(state)
