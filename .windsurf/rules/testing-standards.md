---
# Kiro: Always include this file
inclusion: always

# Windsurf: Apply to Python test files
applies_to:
  - "src/tests/**/*.py"

# GitHub Copilot: Apply to Python test files
applyTo:
  - "src/tests/**/*.py"
---

# Testing Standards for PGMob

## Test Organization

### Directory Structure
```
src/tests/
├── conftest.py                    # Shared fixtures
├── test_*.py                      # Unit tests
└── functional/
    ├── conftest.py               # Integration test fixtures
    └── test_*.py                 # Integration tests
```

### Test File Naming
- Unit tests: `test_<module_name>.py`
- Integration tests: `functional/test_<feature>.py`
- One test file per source module

## Installing Test Dependencies

When running tests for this project, you need to install the psycopg2-binary extra:

```bash
uv sync --extra psycopg2-binary --extra dev
```

## Why psycopg2-binary?

The project supports both `psycopg2` and `psycopg2-binary` as optional dependencies. For testing and development:

- **psycopg2-binary**: Pre-compiled binary package, easier to install, recommended for development
- **psycopg2**: Source package requiring PostgreSQL development libraries, recommended for production

## Running Tests

After installing dependencies:

```bash
# Run all tests
uv run pytest -vv

# Run unit tests only
uv run pytest -m unit -vv

# Run functional tests only (requires Docker, will start container automatically)
uv run pytest -m integration -vv
```

## Type Checking

Only matters for the module itself.

```bash
uv run ty check src/pgmob
```

## Linting

Should apply to both tests and source code.

```bash
uv run ruff check src
uv run ruff format --check src
```

## Test Naming Convention

### Pattern
```python
def test_<feature>_<scenario>_<expected_result>():
    """Test description."""
```

### Examples
```python
def test_table_create_success():
    """Test successful table creation."""

def test_table_create_duplicate_raises_error():
    """Test creating duplicate table raises PostgresError."""

def test_lazy_loading_loads_object_on_first_access():
    """Test lazy loading defers object loading until first access."""

def test_collection_refresh_clears_cache():
    """Test refresh() clears cached objects."""
```

## Test Structure (AAA Pattern)

### Arrange, Act, Assert
```python
def test_table_owner_change():
    """Test changing table owner queues change for alter()."""
    # Arrange
    cluster = Cluster(host="localhost", user="postgres")
    table = cluster.tables["test_table"]
    original_owner = table.owner

    # Act
    table.owner = "new_owner"
    table.alter()
    table.refresh()

    # Assert
    assert table.owner == "new_owner"
    assert table.owner != original_owner
```

## Fixtures

### Shared Fixtures in conftest.py
```python
import pytest
from pgmob import Cluster

@pytest.fixture(scope="session")
def docker_postgres():
    """Start PostgreSQL in Docker for testing."""
    # Setup
    container = start_postgres_container()
    yield container
    # Teardown
    container.stop()

@pytest.fixture
def cluster(docker_postgres):
    """Provide connected cluster for tests."""
    cluster = Cluster(
        host=docker_postgres.host,
        port=docker_postgres.port,
        user="postgres",
        password="test"
    )
    yield cluster
    cluster.adapter.close_connection()

@pytest.fixture
def test_table(cluster):
    """Create test table for tests."""
    cluster.execute("CREATE TABLE test_table (id serial, name text)")
    yield "test_table"
    cluster.execute("DROP TABLE IF EXISTS test_table CASCADE")
```

### Fixture Scopes
- `scope="session"`: Once per test session (Docker containers)
- `scope="module"`: Once per test module
- `scope="function"`: Once per test (default)

## Mocking

### Mock External Dependencies
```python
from unittest.mock import Mock, patch, MagicMock

def test_execute_with_mocked_adapter():
    """Test execute() with mocked adapter."""
    # Arrange
    mock_adapter = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = [(1, "test")]
    mock_adapter.cursor.return_value.__enter__.return_value = mock_cursor

    cluster = Cluster(adapter=mock_adapter)

    # Act
    result = cluster.execute("SELECT * FROM test")

    # Assert
    assert result == [(1, "test")]
    mock_cursor.execute.assert_called_once()
```

### Patch for Testing
```python
@patch('pgmob.cluster.detect_adapter')
def test_cluster_init_detects_adapter(mock_detect):
    """Test Cluster initialization detects adapter."""
    mock_detect.return_value = Mock()

    cluster = Cluster(host="localhost")

    mock_detect.assert_called_once()
```

## Assertions

### Use Descriptive Assertions
```python
# Good: Descriptive message
assert table.owner == "postgres", f"Expected owner 'postgres', got '{table.owner}'"

# Good: pytest assertions with context
assert "test_table" in cluster.tables, "Table should exist in collection"

# Bad: No context
assert table.owner == "postgres"
```

### Multiple Assertions
```python
def test_table_properties():
    """Test table has correct properties."""
    table = cluster.tables["test_table"]

    assert table.name == "test_table"
    assert table.schema == "public"
    assert table.owner == "postgres"
    assert table.oid is not None
```

### Exception Testing
```python
def test_invalid_table_raises_key_error():
    """Test accessing non-existent table raises KeyError."""
    cluster = Cluster(...)

    with pytest.raises(KeyError, match="nonexistent"):
        _ = cluster.tables["nonexistent"]

def test_invalid_sql_raises_postgres_error():
    """Test invalid SQL raises PostgresError."""
    cluster = Cluster(...)

    with pytest.raises(PostgresError):
        cluster.execute("INVALID SQL")
```

## Parametrized Tests

### Test Multiple Scenarios
```python
@pytest.mark.parametrize("load_strategy,expected_loaded", [
    (LoadStrategy.LAZY, False),
    (LoadStrategy.EAGER, True),
    (LoadStrategy.HYBRID, False),
])
def test_collection_loading_strategy(load_strategy, expected_loaded):
    """Test collection respects loading strategy."""
    cluster = Cluster(load_strategy=load_strategy)
    collection = cluster.tables

    is_loaded = len(collection._loaded_keys) > 0
    assert is_loaded == expected_loaded
```

### Test Edge Cases
```python
@pytest.mark.parametrize("value,should_raise", [
    ("", True),           # Empty string
    (None, True),         # None
    ("valid", False),     # Valid value
    ("a" * 1000, False),  # Long string
])
def test_owner_validation(value, should_raise):
    """Test owner property validates input."""
    table = Table(name="test")

    if should_raise:
        with pytest.raises(ValueError):
            table.owner = value
    else:
        table.owner = value
        assert table.owner == value
```

## Integration Tests

### Use Real PostgreSQL
```python
@pytest.mark.integration
def test_table_create_and_drop_integration(cluster):
    """Integration test for table lifecycle."""
    # Create
    table = cluster.tables.new("integration_test")
    table.create()
    cluster.tables.refresh()

    assert "integration_test" in cluster.tables

    # Drop
    cluster.tables["integration_test"].drop()
    cluster.tables.refresh()

    assert "integration_test" not in cluster.tables
```

### Test Against Multiple PostgreSQL Versions
```python
@pytest.mark.parametrize("pg_version", ["10", "11", "12", "13", "14", "15", "16"])
def test_compatibility_with_postgres_version(pg_version):
    """Test compatibility with PostgreSQL version."""
    cluster = start_postgres_cluster(version=pg_version)

    # Test basic operations
    assert cluster.version.major == int(pg_version)
    assert len(cluster.tables) >= 0
```

## Performance Tests

### Benchmark Critical Operations
```python
import time

def test_lazy_loading_performance():
    """Test lazy loading is faster than eager loading."""
    # Lazy loading
    start = time.time()
    cluster_lazy = Cluster(load_strategy=LoadStrategy.LAZY)
    lazy_time = time.time() - start

    # Eager loading
    start = time.time()
    cluster_eager = Cluster(load_strategy=LoadStrategy.EAGER)
    eager_time = time.time() - start

    # Lazy should be significantly faster
    assert lazy_time < eager_time * 0.5
```

### Memory Usage Tests
```python
import tracemalloc

def test_lazy_loading_memory_usage():
    """Test lazy loading uses less memory."""
    # Measure lazy loading
    tracemalloc.start()
    cluster_lazy = Cluster(load_strategy=LoadStrategy.LAZY)
    _ = cluster_lazy.tables.keys()  # Load metadata only
    lazy_memory = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    # Measure eager loading
    tracemalloc.start()
    cluster_eager = Cluster(load_strategy=LoadStrategy.EAGER)
    eager_memory = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    # Lazy should use significantly less memory
    assert lazy_memory < eager_memory * 0.3
```

## Coverage Requirements

### Minimum Coverage
- Overall: >90%
- New code: 100%
- Critical paths: 100%

### Run Coverage
```bash
# Generate coverage report
uv run pytest --cov=pgmob --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

### Coverage Configuration
```ini
# pyproject.toml
[tool.coverage.run]
source = ["src/pgmob"]
omit = [
    "*/tests/*",
    "*/conftest.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.:",
]
```

## Test Markers

### Mark Test Categories
```python
@pytest.mark.unit
def test_unit_test():
    """Unit test."""

@pytest.mark.integration
def test_integration_test():
    """Integration test."""

@pytest.mark.slow
def test_slow_operation():
    """Slow test."""

@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    """Future feature test."""
```

### Run Specific Tests
```bash
# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Skip slow tests
uv run pytest -m "not slow"
```

## Async Tests

### Test Async Operations
```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_collection_loading():
    """Test async parallel collection loading."""
    cluster = AsyncCluster(...)

    collections = await cluster.load_collections_parallel(
        "tables", "roles", "databases"
    )

    assert "tables" in collections
    assert "roles" in collections
    assert "databases" in collections
```

## Test Data Management

### Use Factories for Test Data
```python
def create_test_table(cluster, name="test_table", **kwargs):
    """Factory for creating test tables."""
    defaults = {
        "schema": "public",
        "owner": "postgres",
    }
    defaults.update(kwargs)

    cluster.execute(f"""
        CREATE TABLE {defaults['schema']}.{name} (
            id serial PRIMARY KEY,
            name text
        )
    """)
    return name

def test_with_factory(cluster):
    """Test using factory."""
    table_name = create_test_table(cluster, name="my_test")
    assert table_name in cluster.tables
```

### Cleanup After Tests
```python
@pytest.fixture
def test_database(cluster):
    """Create and cleanup test database."""
    db_name = "test_db"
    cluster.databases.new(db_name).create()

    yield db_name

    # Cleanup
    if db_name in cluster.databases:
        cluster.databases[db_name].drop(force=True)
```

## Continuous Integration

### GitHub Actions Configuration
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]
        postgres-version: ["10", "12", "14", "16"]

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install UV
        run: pip install uv
      - name: Install dependencies
        run: uv sync --all-extras
      - name: Run tests
        run: uv run pytest --cov=pgmob
```

## Test Documentation

### Document Test Purpose
```python
def test_lazy_loading_defers_object_creation():
    """Test lazy loading defers object creation until access.

    This test verifies that when using LAZY loading strategy,
    objects are not created immediately when accessing the collection,
    but only when a specific object is accessed by key.

    This is important for performance when dealing with clusters
    that have thousands of objects.
    """
    cluster = Cluster(load_strategy=LoadStrategy.LAZY)

    # Accessing collection should not load objects
    tables = cluster.tables
    assert len(tables._loaded_keys) == 0

    # Accessing specific table should load only that table
    table = tables["test_table"]
    assert len(tables._loaded_keys) == 1
```

## Common Testing Patterns

### Test Object Lifecycle
```python
def test_object_lifecycle(cluster):
    """Test complete object lifecycle."""
    # Create
    obj = cluster.tables.new("lifecycle_test")
    obj.create()
    assert "lifecycle_test" in cluster.tables

    # Read
    obj = cluster.tables["lifecycle_test"]
    assert obj.name == "lifecycle_test"

    # Update
    obj.owner = "new_owner"
    obj.alter()
    obj.refresh()
    assert obj.owner == "new_owner"

    # Delete
    obj.drop()
    cluster.tables.refresh()
    assert "lifecycle_test" not in cluster.tables
```

### Test Error Recovery
```python
def test_error_recovery(cluster):
    """Test system recovers from errors."""
    # Cause error
    with pytest.raises(PostgresError):
        cluster.execute("INVALID SQL")

    # Verify system still works
    result = cluster.execute("SELECT 1")
    assert result == [(1,)]
```
