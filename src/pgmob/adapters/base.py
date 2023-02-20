from typing import Any, Sequence, Union
from abc import abstractmethod, ABC
from ..sql import Composable


class BaseCursor(ABC):
    """Base Cursor adapter. Abstract class that defines the necessary methods to be overridden by
    the child class that implements Cursor interactions specific to the chosen module.
    """

    # methods that need implementation
    @property
    @abstractmethod
    def statusmessage(self) -> str:
        """Cursor status message"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def closed(self) -> bool:
        """Specifies if the cursor is closed"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def rowcount(self) -> int:
        """Row count of the most recent execute"""
        raise NotImplementedError()

    @abstractmethod
    def close(self) -> None:
        """Close the cursor. The cursor should not be used after this method is called."""
        raise NotImplementedError()

    @abstractmethod
    def execute(self, query: Union[Composable, str], params: tuple = None) -> None:
        """Execute a query with parameters. Should be overridden by the adapter, which should
        provide support for one of the two potential inputs:
            - a query string
            - a Composable object that represent one or more query parts:  SQL, Literal,
              Identifier. Adapter should call the .compose() method of the query object
              to retrieve the parts and reprocess them as needed.

        Args:
            query (Union[Composable, str]): query object or string
            params (tuple): query parameters as a tuple

        Raises:
            NoResultsToFetch: when there are no rows to fetch
            ProgrammingError: when postgres returned an error
            AdapterError: any other Adapter-related error
        """
        raise NotImplementedError()

    @abstractmethod
    def executemany(self, query: Composable, params: Sequence[tuple] = None) -> None:
        """Execute a query with multiple parameter sets. Should be overridden by the adapter, which should
        provide support for all possible Composable objects that represent query parts:
        SQL, Literal, Identifier. Adapter should call the .compose() method of the query object
        to retrieve the parts and reprocess them as needed.
        """
        raise NotImplementedError()

    @abstractmethod
    def mogrify(self, query: Composable, params: tuple = None) -> bytes:
        """Returns a parsed SQL query based on the parameters provided. Should be overridden by the adapter, which should
        provide support for all possible Composable objects that represent query parts:
        SQL, Literal, Identifier. Adapter should call the .compose() method of the query object
        to retrieve the parts and reprocess them as needed.

        Returns:
            bytes: a bytes query string
        """
        raise NotImplementedError()

    @abstractmethod
    def fetchall(self) -> list:
        """Fetch all rows

        Returns:
            list: a ResultSet with the with the query results, if any.

        Raises:
            NoResultsToFetch: when there are no rows to fetch
            ProgrammingError: when postgres returned an error
            AdapterError: any other Adapter-related error
        """
        raise NotImplementedError()

    @abstractmethod
    def fetchone(self) -> Any:
        """Fetch one row

        Returns:
            Any: a single row of the ResultSet

        Raises:
            NoResultsToFetch: when there are no rows to fetch
            ProgrammingError: when postgres returned an error
            AdapterError: any other Adapter-related error
        """
        raise NotImplementedError()

    # default implementations

    def scalar(self, query: Composable, params: tuple = None) -> Any:
        """Same as execute, but returns only the first item of the first row.

        Args:
            query (Any): query object or string
            params (tuple): query parameters as a tuple

        Returns:
            Any: first item of the first row. None if no results have been returned.

        Raises:
            NoResultsToFetch: when there are no rows to fetch
            ProgrammingError: when postgres returned an error
            AdapterError: any other Adapter-related error
        """
        self.execute(query, params)
        result = self.fetchone()
        if len(result) > 0:
            return result[0]
        else:
            return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class BaseLargeObject(ABC):
    """Base Large Object adapter. Abstract class that defines the necessary methods to be overridden by
    the child class that implements Large Object interactions specific to the chosen module.
    """

    # methods that need implementation
    @property
    @abstractmethod
    def closed(self) -> bool:
        """Specifies if the large object is closed"""
        raise NotImplementedError()

    @abstractmethod
    def close(self):
        """Close and deallocate large object"""
        raise NotImplementedError()

    @abstractmethod
    def truncate(self, length: int = 0):
        """Truncate large object

        Args:
            length (int): size to truncate. 0 to remove
        """
        raise NotImplementedError()

    @abstractmethod
    def write(self, data: bytes) -> int:
        """Write large object

        Returns:
            int: number of bytes written
        """
        raise NotImplementedError()

    @abstractmethod
    def read(self) -> Union[str, bytes]:
        """Read large object

        Returns:
            Union[str, bytes]: string or bytes depending on the large object open mode
        """
        raise NotImplementedError()

    @abstractmethod
    def unlink(self):
        """Remove large object"""
        raise NotImplementedError()

    # default implementations

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class BaseAdapter(ABC):
    """Abstract SQL Provider adapter. Defines required properties and methods to be overriden by adapter implementations."""

    # methods that need implementation
    @abstractmethod
    def cursor(self) -> BaseCursor:
        """Retrieve a cursor object"""
        raise NotImplementedError()

    @abstractmethod
    def lobject(self, oid: int, mode: str) -> BaseLargeObject:
        """Retrieve a large object handler object"""
        raise NotImplementedError()

    @abstractmethod
    def connect(self, *args, **kwargs) -> Any:
        """Retrieve a connection object"""
        raise NotImplementedError()

    @abstractmethod
    def commit(self) -> None:
        """Commit the open transaction"""
        raise NotImplementedError()

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the open transaction"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Defines whether the connection is open or closed"""
        raise NotImplementedError()

    @property
    @abstractmethod
    def is_in_transaction(self) -> bool:
        """Defines whether the transaction is currently open"""
        raise NotImplementedError()

    @abstractmethod
    def close_connection(self) -> None:
        """Close the connection"""
        raise NotImplementedError()

    @abstractmethod
    def get_autocommit(self) -> bool:
        """Get autocommit status"""
        raise NotImplementedError()

    @abstractmethod
    def set_autocommit(self, state: bool) -> None:
        """Set autocommit status"""
        raise NotImplementedError()

    # shared methods

    def get_connection(self) -> Any:
        """Retrieve current connection"""
        return self.connection

    def set_connection(self, connection: Any) -> None:
        """Set current connection"""
        self.connection = connection

    @property
    def has_connection(self) -> bool:
        """Whether the connection is defined"""
        return self.connection is not None
