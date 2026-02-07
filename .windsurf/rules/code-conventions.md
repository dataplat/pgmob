---
# Kiro: Always include this file
inclusion: always

# Windsurf: Apply to Python files
applies_to:
  - "**/*.py"

# GitHub Copilot: Apply to Python files
applyTo:
  - "**/*.py"
---

# Code Conventions for PGMob

## Formatting

### Ruff Configuration
- Line length: 110 characters
- Use Ruff for both linting and formatting
- Run before committing: `uv run ruff format . && uv run ruff check --fix .`

### Import Formatting
```python
# Standard library (alphabetical)
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Third-party (alphabetical)
from packaging import Version
import pytest

# Local imports (relative, alphabetical)
from . import util
from ._decorators import get_lazy_property, LAZY_PREFIX
from .errors import PostgresError, AdapterError
from .sql import SQL, Composable, Identifier, Literal

# TYPE_CHECKING imports (avoid circular imports)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..cluster import Cluster
```

### Line Breaks
```python
# Good: Break after opening parenthesis
result = cluster.execute(
    "SELECT * FROM pg_tables WHERE tablename = %s",
    ("mytable",)
)

# Good: Break long method chains
(
    cluster.tables["mytable"]
    .set_owner("new_owner")
    .alter()
    .refresh()
)

# Good: Break long conditionals
if (
    table.owner == "postgres"
    and table.schema == "public"
    and not table.is_temporary
):
    process_table(table)
```

## Naming Conventions

### Classes
```python
# PascalCase for classes
class TableCollection:
    pass

class MetadataProvider:
    pass

# Prefix with underscore for internal/private
class _BaseCollection:
    pass

class _LazyBaseCollection:
    pass
```

### Functions and Methods
```python
# snake_case for functions and methods
def create_table(name: str) -> None:
    pass

def get_table_metadata(oid: int) -> Dict[str, Any]:
    pass

# Prefix with underscore for internal/private
def _fetch_metadata() -> List[Dict]:
    pass

def _build_query() -> SQL:
    pass
```

### Variables
```python
# snake_case for variables
table_name = "users"
connection_string = "host=localhost"
max_retries = 3

# UPPER_SNAKE_CASE for constants
DEFAULT_SCHEMA = "public"
MAX_CONNECTIONS = 100
LAZY_PREFIX = "_pgmlazy_"
```

### Properties
```python
# snake_case for properties
@property
def table_name(self) -> str:
    return self._table_name

@property
def is_connected(self) -> bool:
    return self._is_connected
```

## Type Hints

### Always Use Type Hints
```python
# Function signatures
def execute(
    self,
    query: Union[Composable, str],
    params: Optional[Tuple[Any, ...]] = None
) -> List[Tuple[Any]]:
    pass

# Variable annotations
tables: Dict[str, Table] = {}
count: int = 0
name: Optional[str] = None
```

### Generic Types
```python
from typing import TypeVar, Generic, List, Dict, Optional

T = TypeVar("T")

class Collection(Generic[T]):
    def __init__(self) -> None:
        self._items: Dict[str, T] = {}

    def get(self, key: str) -> Optional[T]:
        return self._items.get(key)

    def add(self, key: str, item: T) -> None:
        self._items[key] = item
```

### TYPE_CHECKING Pattern
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only imported for type checking, not at runtime
    from ..cluster import Cluster
    from .adapters.base import BaseAdapter

class Table:
    def __init__(self, cluster: "Cluster") -> None:
        self.cluster = cluster
```

## Docstrings

### Module Docstrings
```python
"""Table objects for PostgreSQL database management.

This module provides the Table class and TableCollection for managing
PostgreSQL tables through an object-oriented interface.

Example:
    >>> cluster = Cluster(host="localhost")
    >>> table = cluster.tables["users"]
    >>> table.owner = "new_owner"
    >>> table.alter()
"""
```

### Class Docstrings
```python
class Table:
    """Represents a PostgreSQL table.

    Provides methods to create, alter, drop, and query table properties.
    Changes are tracked and applied via the alter() method.

    Args:
        name: Table name
        cluster: Postgres cluster object
        schema: Schema name (default: 'public')
        owner: Table owner
        oid: Table OID

    Attributes:
        name: Table name
        schema: Schema name
        owner: Table owner
        oid: Table OID
        tablespace: Tablespace name
        row_security: Whether row security is enabled

    Example:
        >>> table = cluster.tables["users"]
        >>> table.owner = "app_user"
        >>> table.alter()
    """
```

### Method Docstrings
```python
def create_table(
    self,
    name: str,
    columns: List[Dict[str, Any]],
    *,
    schema: str = "public"
) -> None:
    """Create a new table on the PostgreSQL server.

    Generates and executes a CREATE TABLE statement based on the
    provided column definitions.

    Args:
        name: Table name
        columns: List of column definitions
        schema: Schema name (default: 'public')

    Raises:
        PostgresError: If table creation fails
        ValueError: If column definitions are invalid

    Example:
        >>> cluster.create_table(
        ...     "users",
        ...     [{"name": "id", "type": "serial"}]
        ... )
    """
```

## Error Handling

### Exception Hierarchy
```python
# Base exception
class PostgresError(Exception):
    """Base exception for PGMob errors."""
    pass

# Specific exceptions
class AdapterError(PostgresError):
    """Adapter-specific errors."""
    pass

class ObjectNotFoundError(PostgresError):
    """Object not found in database."""
    pass
```

### Raising Exceptions
```python
# Good: Descriptive error with context
if not result:
    raise PostgresError(
        f"Table '{name}' not found in schema '{schema}'"
    )

# Good: Chain exceptions
try:
    cursor.execute(query)
except Exception as e:
    raise AdapterError(f"Query execution failed: {e}") from e

# Bad: Generic error
raise Exception("Error")  # Don't use generic Exception

# Bad: No context
raise PostgresError("Not found")  # Not descriptive
```

### Exception Handling
```python
# Good: Specific exception handling
try:
    table = cluster.tables["nonexistent"]
except KeyError:
    logger.warning("Table not found, creating new one")
    table = cluster.tables.new("nonexistent")
    table.create()

# Good: Cleanup in finally
try:
    cursor = adapter.cursor()
    cursor.execute(query)
    return cursor.fetchall()
finally:
    cursor.close()

# Better: Use context manager
with adapter.cursor() as cursor:
    cursor.execute(query)
    return cursor.fetchall()
```

## Logging

### Logger Setup
```python
import logging

# Module-level logger
LOGGER = logging.getLogger(__name__)

# Usage
LOGGER.debug("Executing query: %s", query)
LOGGER.info("Connected to cluster: %s", host)
LOGGER.warning("Table not found: %s", name)
LOGGER.error("Failed to execute query: %s", error)
```

### Log Levels
- `DEBUG`: Detailed information for debugging
- `INFO`: General informational messages
- `WARNING`: Warning messages for recoverable issues
- `ERROR`: Error messages for failures
- `CRITICAL`: Critical errors that may cause system failure

### Logging Best Practices
```python
# Good: Use lazy formatting
LOGGER.debug("Query: %s, Params: %s", query, params)

# Bad: String formatting in log call
LOGGER.debug(f"Query: {query}, Params: {params}")  # Evaluated even if not logged

# Good: Don't log sensitive data
LOGGER.info("Connected to host: %s", host)

# Bad: Logging sensitive data
LOGGER.info("Connected with password: %s", password)  # NEVER
```

## Comments

### When to Comment
```python
# Good: Explain WHY, not WHAT
# Use lazy loading to avoid loading thousands of objects on connection
if load_strategy == LoadStrategy.LAZY:
    return self._load_metadata_only()

# Good: Explain complex logic
# PostgreSQL 11+ uses different procedure query format
if self.version >= Version("11.0"):
    sql = util.get_sql("get_procedure_11")
else:
    sql = util.get_sql("get_procedure")

# Bad: Obvious comment
# Set owner to postgres
table.owner = "postgres"  # Comment adds no value

# Bad: Commented-out code
# table.drop()  # Remove commented code, use version control
```

### TODO Comments
```python
# TODO(username): Add support for partitioned tables
# FIXME: This breaks with special characters in table names
# HACK: Workaround for psycopg2 bug #123
# NOTE: This must be called before alter()
```

## Code Organization

### File Structure
```python
"""Module docstring."""

# Imports
import standard_library
import third_party
from . import local

# Constants
DEFAULT_VALUE = 100
MAX_RETRIES = 3

# Private helper functions
def _helper_function():
    pass

# Public classes
class PublicClass:
    pass

# Public functions
def public_function():
    pass
```

### Class Structure
```python
class MyClass:
    """Class docstring."""

    # Class variables
    class_var: int = 0

    def __init__(self):
        """Initialize instance."""
        # Instance variables
        self._private_var = None
        self.public_var = None

    # Properties
    @property
    def my_property(self):
        return self._private_var

    # Public methods
    def public_method(self):
        pass

    # Private methods
    def _private_method(self):
        pass

    # Special methods
    def __repr__(self):
        return f"{self.__class__.__name__}()"

    def __str__(self):
        return self.name
```

## Best Practices

### Use Context Managers
```python
# Good: Automatic resource cleanup
with adapter.cursor() as cursor:
    cursor.execute(query)
    return cursor.fetchall()

# Bad: Manual cleanup
cursor = adapter.cursor()
try:
    cursor.execute(query)
    return cursor.fetchall()
finally:
    cursor.close()
```

### Use Comprehensions
```python
# Good: List comprehension
tables = [t for t in cluster.tables if t.schema == "public"]

# Good: Dict comprehension
table_map = {t.name: t for t in cluster.tables}

# Good: Generator expression for large datasets
total = sum(t.size for t in cluster.tables)

# Bad: Unnecessary loop
tables = []
for t in cluster.tables:
    if t.schema == "public":
        tables.append(t)
```

### Use f-strings
```python
# Good: f-string
message = f"Table '{name}' in schema '{schema}'"

# Good: Multi-line f-string
query = (
    f"SELECT * FROM {schema}.{table} "
    f"WHERE id = {id}"
)

# Bad: % formatting
message = "Table '%s' in schema '%s'" % (name, schema)

# Bad: .format()
message = "Table '{}' in schema '{}'".format(name, schema)
```

### Avoid Mutable Default Arguments
```python
# Good: Use None as default
def create_table(name: str, columns: Optional[List] = None) -> None:
    if columns is None:
        columns = []
    # Use columns

# Bad: Mutable default
def create_table(name: str, columns: List = []) -> None:  # NEVER
    # columns is shared across all calls!
    pass
```

### Use Enums for Constants
```python
from enum import Enum

class LoadStrategy(Enum):
    """Collection loading strategies."""
    LAZY = "lazy"
    EAGER = "eager"
    HYBRID = "hybrid"

# Usage
if strategy == LoadStrategy.LAZY:
    pass
```

### Property vs Method
```python
# Use property for simple attribute access
@property
def name(self) -> str:
    """Table name (property)."""
    return self._name

# Use method for operations that do work
def refresh(self) -> None:
    """Reload from server (method)."""
    self._load_from_server()
```

## Performance Considerations

### Lazy Evaluation
```python
# Good: Lazy property
@property
def tables(self):
    return get_lazy_property(
        self,
        "tables",
        lambda: TableCollection(cluster=self)
    )

# Good: Generator for large datasets
def iter_tables(self):
    for row in self.execute("SELECT * FROM pg_tables"):
        yield Table(*row)
```

### Avoid Repeated Queries
```python
# Good: Cache metadata
def _load_metadata(self):
    if not self._metadata_loaded:
        self._metadata_cache = self._fetch_metadata()
        self._metadata_loaded = True
    return self._metadata_cache

# Bad: Query every time
def get_table_count(self):
    return len(self.execute("SELECT * FROM pg_tables"))  # Slow!
```

### Use Appropriate Data Structures
```python
# Good: Dict for lookups
tables_by_name = {t.name: t for t in tables}
table = tables_by_name["users"]  # O(1)

# Bad: List for lookups
tables_list = list(tables)
table = next(t for t in tables_list if t.name == "users")  # O(n)
```

## Security

### SQL Injection Prevention
```python
# Good: Parameterized query
cluster.execute(
    "SELECT * FROM pg_tables WHERE tablename = %s",
    ("users",)
)

# Good: Use Identifier for names
SQL("SELECT * FROM {table}").format(table=Identifier("users"))

# Bad: String concatenation
query = f"SELECT * FROM {table_name}"  # SQL INJECTION RISK!

# Bad: String formatting
query = "SELECT * FROM %s" % table_name  # SQL INJECTION RISK!
```

### Shell Command Execution
```python
# Good: Use shell.quote()
command = f"pg_dump {self.shell.quote(database)}"

# Good: Use cluster.run_os_command()
result = cluster.run_os_command(f"whoami")

# Bad: Direct string interpolation
command = f"pg_dump {database}"  # SHELL INJECTION RISK!
```

### Credential Handling
```python
# Good: Don't log credentials
LOGGER.info("Connected to %s", host)

# Bad: Logging credentials
LOGGER.info("Connected with password %s", password)  # NEVER!

# Good: Mask in error messages
raise PostgresError(f"Connection failed to {host}")

# Bad: Expose credentials in errors
raise PostgresError(f"Connection failed: {connection_string}")  # May contain password
```
