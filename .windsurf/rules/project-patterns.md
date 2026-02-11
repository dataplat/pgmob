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

# Project-Specific Patterns for PGMob

## Adapter Pattern Usage

### Implementing Adapters
```python
from .adapters.base import BaseAdapter, BaseCursor

class MyAdapter(BaseAdapter):
    """Custom adapter implementation."""

    def connect(self, *args, **kwargs) -> Any:
        """Establish connection."""
        # Implementation
        pass

    def cursor(self) -> BaseCursor:
        """Get cursor object."""
        return MyCursor(self)

    @property
    def is_connected(self) -> bool:
        """Check connection status."""
        return self.connection is not None
```

### Using Adapters
```python
# Auto-detect adapter
from .adapters import detect_adapter

adapter = detect_adapter()
cluster = Cluster(adapter=adapter, host="localhost")

# Specify adapter explicitly
from .adapters.psycopg2 import Psycopg2Adapter

adapter = Psycopg2Adapter()
cluster = Cluster(adapter=adapter, host="localhost")
```

## SQL String Composition

### Loading SQL from Files
```python
from . import util

# Load SQL query
sql = util.get_sql("get_table")

# Load version-specific SQL
sql = util.get_sql("get_procedure", cluster.version)

# Add WHERE clause
sql = sql + SQL(" WHERE c.oid = %s")
result = cluster.execute(sql, (oid,))
```

### Building Dynamic Queries
```python
from .sql import SQL, Identifier, Literal

# Build query with identifiers
query = SQL("SELECT * FROM {schema}.{table}").format(
    schema=Identifier("public"),
    table=Identifier("users")
)

# Build query with conditions
conditions = []
params = []

if schema:
    conditions.append(SQL("schemaname = %s"))
    params.append(schema)

if owner:
    conditions.append(SQL("tableowner = %s"))
    params.append(owner)

if conditions:
    query = query + SQL(" WHERE ") + SQL(" AND ").join(conditions)

result = cluster.execute(query, tuple(params))
```

### Composing Complex Queries
```python
# Build INSERT statement
columns = ["id", "name", "email"]
values_placeholder = SQL(", ").join([SQL("%s")] * len(columns))

query = SQL("INSERT INTO {table} ({columns}) VALUES ({values})").format(
    table=Identifier("users"),
    columns=SQL(", ").join([Identifier(c) for c in columns]),
    values=values_placeholder
)

cluster.execute(query, (1, "John", "john@example.com"))
```

## Lazy Loading Implementation

### Implementing Lazy Collections
```python
from .objects.generic import _LazyBaseCollection

class MyObjectCollection(_LazyBaseCollection[MyObject]):
    """Lazy-loading collection."""

    def _fetch_metadata(self) -> List[Dict[str, Any]]:
        """Fetch lightweight metadata."""
        sql = SQL("""
            SELECT name, schema, oid
            FROM my_objects
            WHERE schema NOT IN ('pg_catalog', 'information_schema')
        """)

        result = self.cluster.execute(sql)
        return [
            {"name": row[0], "schema": row[1], "oid": row[2]}
            for row in result
        ]

    def _fetch_object(self, key: str) -> MyObject:
        """Fetch full object details."""
        oid = self._metadata_cache[key]["oid"]

        sql = util.get_sql("get_my_object") + SQL(" WHERE oid = %s")
        result = self.cluster.execute(sql, (oid,))

        if not result:
            raise PostgresError(f"Object {key} not found")

        return self._map_result(result[0])

    def _get_key(self, item: Dict[str, Any]) -> str:
        """Generate key from metadata."""
        return self._index(name=item["name"], schema=item["schema"])
```

### Using Lazy Collections
```python
# Lazy loading (default)
cluster = Cluster(host="localhost", load_strategy=LoadStrategy.LAZY)

# Check existence without loading
if "mytable" in cluster.tables:  # Fast - uses metadata
    table = cluster.tables["mytable"]  # Loads full object

# Iterate loads on-demand
for table in cluster.tables:  # Loads each table as iterated
    print(table.name)

# Get keys without loading objects
table_names = cluster.tables.keys()  # Fast - uses metadata
```

## Inheritance and Mixins

### Overview

PGMob uses mixins to provide common properties (name, owner, schema, tablespace) to PostgreSQL object classes. Mixins eliminate code duplication and ensure consistent behavior across all object types.

Available mixins:
- **NamedObjectMixin**: Provides `name` property for objects with names
- **OwnedObjectMixin**: Provides `owner` property for objects with owners
- **SchemaObjectMixin**: Provides `schema` property for objects in schemas
- **TablespaceObjectMixin**: Provides `tablespace` property for objects in tablespaces

### Mixin Initialization Pattern

Mixins use explicit initialization methods (`_init_*()`) that must be called in the object's `__init__` method. This avoids constructor conflicts with multiple inheritance.

```python
from .objects.mixins import (
    NamedObjectMixin,
    OwnedObjectMixin,
    SchemaObjectMixin,
    TablespaceObjectMixin
)
from .objects.generic import _DynamicObject, _CollectionChild

class Table(
    NamedObjectMixin,
    OwnedObjectMixin,
    SchemaObjectMixin,
    TablespaceObjectMixin,
    _DynamicObject,
    _CollectionChild
):
    """Table object with mixin properties."""

    def __init__(
        self,
        name: str,
        schema: str = "public",
        owner: Optional[str] = None,
        cluster: "Cluster" = None,
        parent: "TableCollection" = None,
        oid: Optional[int] = None
    ):
        # Initialize base classes
        super().__init__(kind="TABLE", cluster=cluster, oid=oid, name=name, schema=schema)
        _CollectionChild.__init__(self, parent=parent)

        # Initialize mixins - REQUIRED
        self._init_name(name)
        self._init_owner(owner)
        self._init_schema(schema)
        self._init_tablespace(None)

        # Object-specific attributes
        self._row_security: bool = False
```

### Creating Objects with Mixins

#### Example 1: Object with Name, Owner, and Schema

```python
from .objects.mixins import NamedObjectMixin, OwnedObjectMixin, SchemaObjectMixin
from .objects.generic import _DynamicObject, _CollectionChild

class Sequence(
    NamedObjectMixin,
    OwnedObjectMixin,
    SchemaObjectMixin,
    _DynamicObject,
    _CollectionChild
):
    """Sequence object."""

    def __init__(
        self,
        name: str,
        schema: str = "public",
        owner: Optional[str] = None,
        cluster: "Cluster" = None,
        parent: "SequenceCollection" = None,
        oid: Optional[int] = None
    ):
        super().__init__(kind="SEQUENCE", cluster=cluster, oid=oid, name=name, schema=schema)
        _CollectionChild.__init__(self, parent=parent)

        # Initialize mixins
        self._init_name(name)
        self._init_owner(owner)
        self._init_schema(schema)

        # Sequence-specific attributes
        self._start_value: Optional[int] = None
        self._increment_by: Optional[int] = None
```

#### Example 2: Object with Only Name and Owner

```python
from .objects.mixins import NamedObjectMixin, OwnedObjectMixin
from .objects.generic import _DynamicObject, _CollectionChild

class Schema(
    NamedObjectMixin,
    OwnedObjectMixin,
    _DynamicObject,
    _CollectionChild
):
    """Schema object (does NOT inherit SchemaObjectMixin)."""

    def __init__(
        self,
        name: str,
        owner: Optional[str] = None,
        cluster: "Cluster" = None,
        parent: "SchemaCollection" = None,
        oid: Optional[int] = None
    ):
        super().__init__(kind="SCHEMA", cluster=cluster, oid=oid, name=name)
        _CollectionChild.__init__(self, parent=parent)

        # Initialize mixins
        self._init_name(name)
        self._init_owner(owner)
```

#### Example 3: Object with Only Name

```python
from .objects.mixins import NamedObjectMixin
from .objects.generic import _DynamicObject, _CollectionChild

class Role(
    NamedObjectMixin,
    _DynamicObject,
    _CollectionChild
):
    """Role object."""

    def __init__(
        self,
        name: str,
        cluster: "Cluster" = None,
        parent: "RoleCollection" = None,
        oid: Optional[int] = None,
        password: Optional[str] = None
    ):
        super().__init__(kind="ROLE", cluster=cluster, oid=oid, name=name)
        _CollectionChild.__init__(self, parent=parent)

        # Initialize mixin
        self._init_name(name)

        # Role-specific attributes
        self._password = password
        self._superuser: bool = False
        self._login: bool = False
```

### Which Mixins to Use

Choose mixins based on the PostgreSQL object type:

| Object Type | NamedObjectMixin | OwnedObjectMixin | SchemaObjectMixin | TablespaceObjectMixin |
|-------------|------------------|------------------|-------------------|----------------------|
| Table       | ✓                | ✓                | ✓                 | ✓                    |
| View        | ✓                | ✓                | ✓                 | ✗                    |
| Sequence    | ✓                | ✓                | ✓                 | ✗                    |
| Schema      | ✓                | ✓                | ✗                 | ✗                    |
| Role        | ✓                | ✗                | ✗                 | ✗                    |
| Database    | ✓                | ✓                | ✗                 | ✓                    |
| Procedure   | ✓                | ✓                | ✓                 | ✗                    |

**Note**: Schema objects do NOT inherit from SchemaObjectMixin (schemas don't belong to schemas).

### Using Mixin Properties

Mixin properties work exactly like regular properties with change tracking:

```python
# Get property value
table = cluster.tables["users"]
print(table.name)    # From NamedObjectMixin
print(table.owner)   # From OwnedObjectMixin
print(table.schema)  # From SchemaObjectMixin

# Set property value (queues change for alter())
table.owner = "new_owner"
table.schema = "app_schema"
table.alter()  # Apply changes to database
```

### Change Tracking Pattern
```python
class MyObject(_DynamicObject):
    """Object with change tracking."""

    @property
    def custom_property(self) -> str:
        return self._custom_property

    @custom_property.setter
    def custom_property(self, value: str) -> None:
        """Set property. Queues change for alter()."""
        if self._custom_property != value:
            self._changes["custom_property"] = generic._SQLChange(
                obj=self,
                sql=SQL("ALTER MY_OBJECT {fqn} SET CUSTOM {value}").format(
                    fqn=self._sql_fqn(),
                    value=Literal(value)
                )
            )
            self._custom_property = value

    def alter(self) -> None:
        """Apply pending changes."""
        super().alter()  # Applies all queued changes
```

## Provider Pattern

### Implementing Metadata Providers
```python
from .providers.base import MetadataProvider

class CustomMetadataProvider(MetadataProvider):
    """Custom metadata provider."""

    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster)
        self._cache: Dict[str, Any] = {}

    def get_tables(self, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get table metadata."""
        cache_key = f"tables:{schema}"

        if cache_key not in self._cache:
            sql = util.get_sql("get_table")
            if schema:
                sql += SQL(" WHERE n.nspname = %s")
                result = self.cluster.execute(sql, (schema,))
            else:
                result = self.cluster.execute(sql)

            self._cache[cache_key] = [
                self._map_table_row(row) for row in result
            ]

        return self._cache[cache_key]

    def invalidate_cache(self, object_type: Optional[str] = None) -> None:
        """Invalidate cache."""
        if object_type:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{object_type}:")]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()
```

### Using Providers
```python
# Use default provider
cluster = Cluster(host="localhost")

# Use custom provider
from .providers.custom import CustomMetadataProvider

provider = CustomMetadataProvider(cluster)
cluster.metadata_provider = provider

# Access through provider
tables = cluster.metadata_provider.get_tables(schema="public")
```

## Version-Specific Handling

### Version Detection
```python
from packaging import Version

# Check version
if cluster.version >= Version("11.0"):
    # Use PostgreSQL 11+ features
    sql = util.get_sql("get_procedure_11")
else:
    # Use older query
    sql = util.get_sql("get_procedure")
```

### Version-Specific SQL Files
```
src/pgmob/scripts/sql/
├── get_procedure.sql       # Default (PostgreSQL 10+)
└── get_procedure_11.sql    # PostgreSQL 11+
```

```python
# Load version-specific SQL
sql = util.get_sql("get_procedure", cluster.version)
```

## Error Handling Patterns

### Custom Exceptions
```python
from .errors import PostgresError

class ObjectNotFoundError(PostgresError):
    """Raised when object not found."""
    pass

class PermissionDeniedError(PostgresError):
    """Raised when operation not permitted."""
    pass

# Usage
if not result:
    raise ObjectNotFoundError(
        f"Table '{name}' not found in schema '{schema}'"
    )
```

### Error Recovery
```python
def execute_with_retry(
    self,
    query: str,
    params: tuple = None,
    max_retries: int = 3
) -> List[Tuple[Any]]:
    """Execute query with retry logic."""
    for attempt in range(max_retries):
        try:
            return self.execute(query, params)
        except AdapterError as e:
            if attempt == max_retries - 1:
                raise

            LOGGER.warning(
                "Query failed (attempt %d/%d): %s",
                attempt + 1,
                max_retries,
                e
            )

            # Reconnect if connection lost
            if not self.adapter.is_connected:
                self._acquire_connection()
```

## Context Manager Patterns

### Transaction Management
```python
# Use context manager for transactions
with cluster._no_autocommit():
    # Multiple operations in single transaction
    cluster.execute("INSERT INTO users VALUES (%s, %s)", (1, "John"))
    cluster.execute("INSERT INTO logs VALUES (%s, %s)", (1, "Created"))
    # Automatically commits on exit
```

### Resource Management
```python
# Cursor management
with cluster.adapter.cursor() as cursor:
    cursor.execute(query)
    result = cursor.fetchall()
# Cursor automatically closed

# Connection management
with Cluster(host="localhost") as cluster:
    # Use cluster
    tables = cluster.tables
# Connection automatically closed
```

## Async Patterns

### Async Operations
```python
import asyncio

# Async collection loading
async def load_all_collections():
    cluster = AsyncCluster(...)

    collections = await cluster.load_collections_parallel(
        "tables", "roles", "databases", "schemas"
    )

    return collections

# Run async operation
collections = asyncio.run(load_all_collections())
```

### Sync Wrapper
```python
def load_collections(self, *names: str, parallel: bool = False):
    """Load collections with optional parallel execution."""
    if parallel and self.enable_async:
        return asyncio.run(self._load_collections_async(*names))
    else:
        return self._load_collections_sync(*names)
```

## Testing Patterns

### Fixture Patterns
```python
@pytest.fixture
def cluster():
    """Provide test cluster."""
    cluster = Cluster(host="localhost", user="postgres")
    yield cluster
    cluster.adapter.close_connection()

@pytest.fixture
def test_table(cluster):
    """Provide test table."""
    table_name = "test_table"
    cluster.execute(f"CREATE TABLE {table_name} (id serial, name text)")

    yield table_name

    cluster.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
```

### Mock Patterns
```python
from unittest.mock import Mock, patch

@patch('pgmob.adapters.detect_adapter')
def test_with_mock_adapter(mock_detect):
    """Test with mocked adapter."""
    mock_adapter = Mock()
    mock_adapter.is_connected = True
    mock_detect.return_value = mock_adapter

    cluster = Cluster(host="localhost")

    assert cluster.adapter == mock_adapter
```

## Logging Patterns

### Module Logger
```python
import logging

LOGGER = logging.getLogger(__name__)

class MyClass:
    def my_method(self):
        LOGGER.debug("Executing method: %s", self.name)
        LOGGER.info("Operation completed successfully")
```

### Structured Logging
```python
LOGGER.info(
    "Table created",
    extra={
        "table_name": table.name,
        "schema": table.schema,
        "owner": table.owner,
        "operation": "create"
    }
)
```

## Performance Patterns

### Caching
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_table_metadata(oid: int) -> Dict[str, Any]:
    """Get table metadata with caching."""
    sql = util.get_sql("get_table") + SQL(" WHERE c.oid = %s")
    result = cluster.execute(sql, (oid,))
    return dict(zip(COLUMNS, result[0]))
```

### Batch Operations
```python
def bulk_alter_owner(self, tables: List[Table], new_owner: str) -> None:
    """Bulk alter table owners."""
    statements = []

    for table in tables:
        if table.owner != new_owner:
            statements.append(
                SQL("ALTER TABLE {table} OWNER TO {owner}").format(
                    table=table._sql_fqn(),
                    owner=Identifier(new_owner)
                )
            )

    if statements:
        # Execute all in single transaction
        with self._no_autocommit():
            for stmt in statements:
                self.execute(stmt)
```

## Development Environment Setup

### CRITICAL: Initial Setup Required

Before starting any development work, you MUST set up the development environment:

```bash
# Install all dependencies including dev tools
uv sync --extra dev --extra psycopg2-binary
```

This command:
- Installs all project dependencies
- Installs development tools (pytest, ruff, ty, etc.)
- Installs the psycopg2-binary adapter for PostgreSQL

Run this command once at the start of development or whenever dependencies change.

## Code Quality Verification

### CRITICAL: Always Run After Code Changes

After implementing ANY code change to the codebase, you MUST run the following checks in order:

1. **Unit Tests**: Verify functionality works correctly
2. **Linting**: Ensure code style compliance
3. **Type Checks**: Verify type safety

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest src/tests/test_mixins.py

# Run with coverage
uv run pytest --cov=src/pgmob --cov-report=term-missing

# Run tests matching pattern
uv run pytest -k "test_mixin"
```

### Running Linting

```bash
# Run ruff linter (checks code style and common issues)
uv run ruff check src/

# Run ruff with auto-fix
uv run ruff check --fix src/

# Check specific file
uv run ruff check src/pgmob/objects/mixins.py
```

### Running Type Checks

```bash
# Run ty type checker
uv run ty check

# Type checking is project-wide, no single file option
```

### Complete Verification Workflow

After making code changes, run this complete workflow:

```bash
# 1. Run tests
uv run pytest

# 2. Run linting
uv run ruff check src/

# 3. Run type checks
uv run ty check
```

# 3. Run type checks
uv run ty check
```

If any check fails, fix the issues before proceeding. Do not consider a code change complete until all three checks pass.

### Handling Check Failures

**Test Failures:**
- Review the test output to understand what failed
- Fix the implementation or update tests if requirements changed
- Re-run tests to verify the fix

**Linting Failures:**
- Use `uv run ruff check --fix` to auto-fix simple issues
- Manually fix remaining issues following PEP 8 and project conventions
- Re-run linting to verify compliance

**Type Check Failures:**
- Add missing type hints
- Fix incorrect type annotations
- Use `# type: ignore` only as a last resort with a comment explaining why
- Re-run type checks to verify fixes
- Note: Type warnings in mixin classes about `_set_ephemeral_attr` expecting `_DynamicObject` are expected and safe to ignore, as mixins are only used with classes that inherit from `_DynamicObject`

## Documentation Patterns

### Example in Docstring
```python
def create_table(self, name: str, columns: List[Dict]) -> None:
    """Create a new table.

    Args:
        name: Table name
        columns: Column definitions

    Example:
        >>> cluster.create_table(
        ...     "users",
        ...     [
        ...         {"name": "id", "type": "serial", "primary_key": True},
        ...         {"name": "username", "type": "varchar(50)", "nullable": False},
        ...         {"name": "email", "type": "varchar(100)"},
        ...     ]
        ... )
    """
```

### Type Hints in Documentation
```python
from typing import Union, Optional, List

def execute(
    self,
    query: Union[Composable, str],
    params: Optional[Tuple[Any, ...]] = None
) -> List[Tuple[Any]]:
    """Execute SQL query.

    Args:
        query: SQL query string or Composable object
        params: Query parameters as tuple

    Returns:
        List of tuples containing query results

    Raises:
        PostgresError: If query execution fails
        AdapterError: If adapter error occurs
    """
```
