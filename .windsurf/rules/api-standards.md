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

# API Standards for PGMob

## Method Naming Conventions

### CRUD Operations
- `create()`: Create object on PostgreSQL server
- `drop(cascade: bool = False)`: Remove object from server
- `alter()`: Apply pending changes to server
- `refresh()`: Reload object state from server
- `script(as_composable: bool = False)`: Generate DDL

### Collection Operations
- `new(**kwargs)`: Create ephemeral object (not yet on server)
- `add(obj)`: Add object to collection and create on server
- `refresh()`: Reload all objects from server
- `keys()`: Get all object keys without loading objects

### Query Operations
- `execute(query, params)`: Execute SQL query
- `execute_with_cursor(task)`: Execute task with cursor
- `execute_many(queries)`: Execute multiple queries (async)

## Return Types

### Methods that Modify State
```python
def create(self) -> None:
    """Create object on server. Returns None."""

def alter(self) -> None:
    """Apply changes. Returns None."""

def drop(self, cascade: bool = False) -> None:
    """Drop object. Returns None."""
```

### Query Methods
```python
def execute(self, query: str, params: tuple = None) -> List[Tuple[Any]]:
    """Execute query. Returns list of tuples or empty list."""

def fetchall(self) -> List[Tuple[Any]]:
    """Fetch all rows. Returns list of tuples."""
```

### Object Getters
```python
def __getitem__(self, key: str) -> T:
    """Get object by key. Raises KeyError if not found."""

def get(self, key: str, default: T = None) -> Optional[T]:
    """Get object by key. Returns default if not found."""
```

## Parameter Conventions

### Required vs Optional
- Required parameters: positional or keyword
- Optional parameters: keyword-only with defaults
- Use `Optional[T]` for nullable types

```python
def __init__(
    self,
    name: str,                    # Required positional
    cluster: "Cluster" = None,    # Optional with default
    *,                            # Keyword-only marker
    owner: Optional[str] = None,  # Optional keyword-only
    schema: str = "public"        # Optional with default
):
```

### Boolean Flags
- Use descriptive names: `cascade`, `force`, `if_exists`
- Default to safe behavior (False for destructive operations)
- Document behavior for both True and False

```python
def drop(self, cascade: bool = False, if_exists: bool = False) -> None:
    """Drop object.

    Args:
        cascade: Drop dependent objects
        if_exists: Don't raise error if object doesn't exist
    """
```

## Error Handling

### Exception Types
```python
from .errors import PostgresError, AdapterError

# Use PostgresError for database-related errors
if not result:
    raise PostgresError(f"Table '{name}' not found in schema '{schema}'")

# Use AdapterError for adapter-specific errors
try:
    cursor.execute(query)
except Exception as e:
    raise AdapterError(f"Query execution failed: {e}")
```

### Error Messages
- Include context: object name, operation, parameters
- Provide actionable information
- Don't expose sensitive data (passwords, connection strings)
- Use f-strings for formatting

```python
# Good
raise PostgresError(
    f"Failed to create table '{self.name}' in schema '{self.schema}': {error}"
)

# Bad
raise PostgresError("Error")  # Not descriptive
raise PostgresError(f"Failed with password {password}")  # Exposes sensitive data
```

## Type Hints

### Always Use Type Hints
```python
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Union

if TYPE_CHECKING:
    from ..cluster import Cluster

def execute(
    self,
    query: Union[Composable, str],
    params: Optional[Tuple[Any, ...]] = None
) -> List[Tuple[Any]]:
    """Execute query with type hints."""
```

### Generic Types
```python
from typing import TypeVar, Generic

T = TypeVar("T")

class Collection(Generic[T]):
    def __getitem__(self, key: str) -> T:
        ...
```

## Docstring Format

### Google Style
```python
def create_table(
    self,
    name: str,
    columns: List[Dict[str, Any]],
    *,
    schema: str = "public",
    if_not_exists: bool = False
) -> None:
    """Create a new table on the PostgreSQL server.

    This method generates and executes a CREATE TABLE statement based on
    the provided column definitions.

    Args:
        name: Table name
        columns: List of column definitions with 'name', 'type', and optional
            'nullable', 'default' keys
        schema: Schema name (default: 'public')
        if_not_exists: Don't raise error if table exists

    Raises:
        PostgresError: If table creation fails
        ValueError: If column definitions are invalid

    Example:
        >>> cluster.create_table(
        ...     "users",
        ...     [
        ...         {"name": "id", "type": "serial", "nullable": False},
        ...         {"name": "username", "type": "varchar(50)"},
        ...     ]
        ... )
    """
```

## Property Patterns

### Read-Only Properties
```python
@property
def oid(self) -> Optional[int]:
    """Object ID (read-only)."""
    return self._oid
```

### Read-Write Properties with Validation
```python
@property
def owner(self) -> Optional[str]:
    """Object owner."""
    return self._owner

@owner.setter
def owner(self, value: str) -> None:
    """Set object owner. Queues change for alter()."""
    if not value:
        raise ValueError("Owner cannot be empty")
    generic._set_ephemeral_attr(self, "owner", value)
```

### Lazy Properties
```python
from ._decorators import get_lazy_property

@property
def tables(self) -> TableCollection:
    """Table collection (lazy-loaded)."""
    return get_lazy_property(
        self,
        "tables",
        lambda: TableCollection(cluster=self, load_strategy=self.load_strategy)
    )
```

## Context Managers

### Use Context Managers for Resources
```python
# Cursor management
with cluster.adapter.cursor() as cursor:
    cursor.execute(query)
    return cursor.fetchall()

# Transaction management
with cluster._no_autocommit():
    # Multiple operations in transaction
    cluster.execute(query1)
    cluster.execute(query2)
```

## Async API Conventions

### Async Method Naming
- Prefix with `async_` or use separate async module
- Provide sync wrappers when appropriate

```python
# Async method
async def load_collections_parallel(self, *names: str) -> Dict[str, Any]:
    """Load multiple collections in parallel."""

# Sync wrapper
def load_collections(self, *names: str, parallel: bool = False) -> Dict[str, Any]:
    """Load collections. Use parallel=True for async loading."""
    if parallel and self.enable_async:
        return asyncio.run(self.load_collections_parallel(*names))
    else:
        return self._load_collections_sequential(*names)
```

## Deprecation

### Deprecation Warnings
```python
import warnings

def old_method(self):
    """Deprecated method."""
    warnings.warn(
        "old_method() is deprecated. Use new_method() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return self.new_method()
```

### Version Information
- Document when feature was added: `.. versionadded:: 0.2.0`
- Document when deprecated: `.. deprecated:: 0.2.0`
- Remove after 2 major versions

## Backward Compatibility

### Feature Flags
```python
def __init__(
    self,
    *args,
    load_strategy: LoadStrategy = LoadStrategy.LAZY,
    legacy_mode: bool = False,
    **kwargs
):
    """Initialize cluster.

    Args:
        load_strategy: Collection loading strategy
        legacy_mode: Use v0.1.x behavior (deprecated)
    """
    if legacy_mode:
        warnings.warn(
            "legacy_mode is deprecated. Use load_strategy=LoadStrategy.EAGER",
            DeprecationWarning
        )
        load_strategy = LoadStrategy.EAGER
```

## Testing API

### Public API Must Have Tests
```python
def test_table_create():
    """Test table creation via API."""
    cluster = Cluster(...)
    table = cluster.tables.new("test_table")
    table.create()

    assert "test_table" in cluster.tables
    assert cluster.tables["test_table"].owner == "postgres"
```

### Test Error Cases
```python
def test_table_create_duplicate_raises_error():
    """Test creating duplicate table raises error."""
    cluster = Cluster(...)
    cluster.tables.new("test_table").create()

    with pytest.raises(PostgresError, match="already exists"):
        cluster.tables.new("test_table").create()
```
