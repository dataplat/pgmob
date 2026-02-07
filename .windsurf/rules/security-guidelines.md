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

# Security Guidelines for PGMob

## SQL Injection Prevention

### Always Use Parameterized Queries
```python
# SECURE: Parameterized query
cluster.execute(
    "SELECT * FROM pg_tables WHERE tablename = %s",
    ("users",)
)

# SECURE: Multiple parameters
cluster.execute(
    "SELECT * FROM pg_tables WHERE tablename = %s AND schemaname = %s",
    ("users", "public")
)

# INSECURE: String concatenation
query = f"SELECT * FROM pg_tables WHERE tablename = '{table_name}'"  # NEVER!
cluster.execute(query)

# INSECURE: String formatting
query = "SELECT * FROM pg_tables WHERE tablename = '%s'" % table_name  # NEVER!
cluster.execute(query)
```

### Use SQL Composition for Identifiers
```python
from .sql import SQL, Identifier, Literal

# SECURE: Use Identifier for table/column names
query = SQL("SELECT * FROM {table} WHERE {column} = %s").format(
    table=Identifier("users"),
    column=Identifier("username")
)
cluster.execute(query, ("admin",))

# SECURE: Use Literal for SQL literals
query = SQL("SET TIME ZONE {tz}").format(tz=Literal("UTC"))
cluster.execute(query)

# INSECURE: String interpolation for identifiers
query = f"SELECT * FROM {table_name}"  # SQL INJECTION RISK!
```

### Validate User Input
```python
# SECURE: Validate before use
def get_table(name: str) -> Table:
    # Validate table name format
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError(f"Invalid table name: {name}")

    return cluster.tables[name]

# SECURE: Whitelist allowed values
ALLOWED_SCHEMAS = {"public", "app", "data"}

def get_schema(name: str) -> Schema:
    if name not in ALLOWED_SCHEMAS:
        raise ValueError(f"Schema not allowed: {name}")

    return cluster.schemas[name]
```

## Shell Command Injection Prevention

### Use Shell Quoting
```python
from .os import ShellEnv

shell = ShellEnv()

# SECURE: Use shell.quote()
database = "my_database"
command = f"pg_dump {shell.quote(database)}"

# SECURE: Quote all user-provided arguments
command = f"pg_dump -h {shell.quote(host)} -U {shell.quote(user)} {shell.quote(database)}"

# INSECURE: Direct interpolation
command = f"pg_dump {database}"  # SHELL INJECTION RISK!
```

### Use cluster.run_os_command()
```python
# SECURE: Use cluster method
result = cluster.run_os_command("whoami")

# SECURE: With proper quoting
database = user_input
result = cluster.run_os_command(f"pg_dump {shell.quote(database)}")

# INSECURE: Direct subprocess
import subprocess
subprocess.run(f"pg_dump {database}", shell=True)  # NEVER!
```

### Avoid Shell=True
```python
import subprocess

# SECURE: Use list of arguments
subprocess.run(["pg_dump", "-d", database])

# INSECURE: shell=True with string
subprocess.run(f"pg_dump -d {database}", shell=True)  # NEVER!
```

## Credential Management

### Never Log Credentials
```python
import logging

LOGGER = logging.getLogger(__name__)

# SECURE: Log without credentials
LOGGER.info("Connecting to host: %s", host)
LOGGER.info("Connected as user: %s", user)

# INSECURE: Logging credentials
LOGGER.info("Password: %s", password)  # NEVER!
LOGGER.debug("Connection string: %s", connstring)  # May contain password!
```

### Mask Credentials in Error Messages
```python
# SECURE: Generic error message
try:
    cluster.connect(host=host, user=user, password=password)
except Exception as e:
    raise PostgresError(f"Connection failed to {host}") from e

# INSECURE: Expose credentials
try:
    cluster.connect(connstring)
except Exception as e:
    raise PostgresError(f"Connection failed: {connstring}") from e  # May contain password!
```

### Use Environment Variables
```python
import os

# SECURE: Read from environment
password = os.environ.get("PGPASSWORD")
cluster = Cluster(
    host="localhost",
    user="postgres",
    password=password
)

# INSECURE: Hardcoded credentials
cluster = Cluster(
    host="localhost",
    user="postgres",
    password="secret123"  # NEVER!
)
```

### Secure Password Storage
```python
# SECURE: Use keyring or secrets manager
import keyring

password = keyring.get_password("pgmob", "postgres")
cluster = Cluster(host="localhost", user="postgres", password=password)

# SECURE: Use .pgpass file
# PostgreSQL will automatically read from ~/.pgpass
cluster = Cluster(host="localhost", user="postgres")
```

## Connection Security

### Use SSL/TLS
```python
# SECURE: Require SSL
cluster = Cluster(
    host="production.example.com",
    user="app_user",
    password=password,
    sslmode="require"
)

# SECURE: Verify certificate
cluster = Cluster(
    host="production.example.com",
    user="app_user",
    password=password,
    sslmode="verify-full",
    sslrootcert="/path/to/ca.crt"
)
```

### Limit Connection Permissions
```python
# SECURE: Use least privilege principle
# Connect as read-only user for queries
readonly_cluster = Cluster(
    host="localhost",
    user="readonly_user",
    password=readonly_password
)

# Use admin user only when needed
admin_cluster = Cluster(
    host="localhost",
    user="postgres",
    password=admin_password
)
```

## Input Validation

### Validate All User Input
```python
# SECURE: Validate table name
def validate_table_name(name: str) -> None:
    if not name:
        raise ValueError("Table name cannot be empty")

    if len(name) > 63:  # PostgreSQL limit
        raise ValueError("Table name too long")

    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValueError("Invalid table name format")

# SECURE: Validate schema name
def validate_schema_name(name: str) -> None:
    if name not in ALLOWED_SCHEMAS:
        raise ValueError(f"Schema not allowed: {name}")
```

### Sanitize File Paths
```python
from pathlib import Path

# SECURE: Validate file path
def validate_backup_path(path: str) -> Path:
    backup_dir = Path("/var/backups/pgmob")
    full_path = (backup_dir / path).resolve()

    # Prevent directory traversal
    if not str(full_path).startswith(str(backup_dir)):
        raise ValueError("Invalid backup path")

    return full_path

# Usage
backup_path = validate_backup_path(user_provided_path)
```

## Access Control

### Check Permissions Before Operations
```python
# SECURE: Check if user has permission
def drop_table(cluster: Cluster, table_name: str) -> None:
    table = cluster.tables[table_name]

    # Check if current user is owner or superuser
    current_user = cluster.execute("SELECT current_user")[0][0]
    if table.owner != current_user and not is_superuser(cluster):
        raise PermissionError(f"User {current_user} cannot drop table {table_name}")

    table.drop()
```

### Implement Role-Based Access
```python
from enum import Enum

class Permission(Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

class SecureCluster:
    def __init__(self, cluster: Cluster, user_permissions: set[Permission]):
        self.cluster = cluster
        self.permissions = user_permissions

    def execute(self, query: str, params: tuple = None):
        # Check if query is read-only
        if query.strip().upper().startswith(("SELECT", "SHOW")):
            if Permission.READ not in self.permissions:
                raise PermissionError("User does not have READ permission")
        else:
            if Permission.WRITE not in self.permissions:
                raise PermissionError("User does not have WRITE permission")

        return self.cluster.execute(query, params)
```

## Secure Defaults

### Use Secure Defaults
```python
# SECURE: Default to safe behavior
def drop_table(self, cascade: bool = False, force: bool = False) -> None:
    """Drop table.

    Args:
        cascade: Drop dependent objects (default: False)
        force: Force drop without confirmation (default: False)
    """
    if not force:
        # Require explicit confirmation for destructive operations
        raise ValueError("Set force=True to confirm table drop")

    # ... drop logic
```

### Disable Dangerous Features by Default
```python
class Cluster:
    def __init__(
        self,
        *args,
        allow_shell_commands: bool = False,  # Disabled by default
        allow_file_operations: bool = False,  # Disabled by default
        **kwargs
    ):
        self.allow_shell_commands = allow_shell_commands
        self.allow_file_operations = allow_file_operations

    def run_os_command(self, command: str) -> str:
        if not self.allow_shell_commands:
            raise PermissionError("Shell commands are disabled")

        # ... execute command
```

## Audit Logging

### Log Security-Relevant Events
```python
import logging

SECURITY_LOGGER = logging.getLogger("pgmob.security")

# Log authentication attempts
def connect(self, *args, **kwargs):
    try:
        result = self._connect(*args, **kwargs)
        SECURITY_LOGGER.info(
            "Successful connection: user=%s, host=%s",
            kwargs.get("user"),
            kwargs.get("host")
        )
        return result
    except Exception as e:
        SECURITY_LOGGER.warning(
            "Failed connection attempt: user=%s, host=%s, error=%s",
            kwargs.get("user"),
            kwargs.get("host"),
            str(e)
        )
        raise

# Log privilege escalation
def become_role(self, role: str):
    SECURITY_LOGGER.info(
        "Role change: from=%s, to=%s",
        self.current_user,
        role
    )
    self.execute(f"SET ROLE {Identifier(role)}")
```

### Log Destructive Operations
```python
def drop_table(self, cascade: bool = False):
    SECURITY_LOGGER.warning(
        "Dropping table: name=%s, schema=%s, cascade=%s, user=%s",
        self.name,
        self.schema,
        cascade,
        self.cluster.current_user
    )

    # ... drop logic
```

## Rate Limiting

### Implement Rate Limiting
```python
from time import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests: int = 100, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self.requests = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time()
        # Remove old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if now - req_time < self.window
        ]

        # Check limit
        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

# Usage
rate_limiter = RateLimiter(max_requests=100, window=60)

def execute(self, query: str, params: tuple = None):
    if not rate_limiter.check(self.current_user):
        raise PermissionError("Rate limit exceeded")

    return self._execute(query, params)
```

## Secure Configuration

### Configuration Validation
```python
from typing import Dict, Any

def validate_config(config: Dict[str, Any]) -> None:
    """Validate cluster configuration for security issues."""

    # Check for insecure SSL mode
    if config.get("sslmode") in (None, "disable", "allow"):
        raise ValueError("Insecure SSL mode. Use 'require' or 'verify-full'")

    # Check for hardcoded credentials
    if "password" in config:
        raise ValueError("Do not hardcode passwords in configuration")

    # Check for overly permissive settings
    if config.get("allow_shell_commands") and config.get("allow_file_operations"):
        raise ValueError("Dangerous: both shell commands and file operations enabled")
```

## Dependency Security

### Pin Dependencies
```toml
# pyproject.toml
[project]
dependencies = [
    "psycopg2-binary>=2.9.5,<3.0",  # Pin major version
    "packaging>=21.3,<24.0",
]
```

### Regular Security Audits
```bash
# Check for known vulnerabilities
uv pip check

# Update dependencies
uv sync --upgrade

# Audit with safety
uv run safety check
```

## Testing Security

### Security Test Cases
```python
def test_sql_injection_prevention():
    """Test SQL injection is prevented."""
    cluster = Cluster(...)

    # Attempt SQL injection
    malicious_input = "users'; DROP TABLE users; --"

    # Should not execute DROP TABLE
    with pytest.raises(KeyError):
        cluster.tables[malicious_input]

def test_shell_injection_prevention():
    """Test shell injection is prevented."""
    cluster = Cluster(...)

    # Attempt shell injection
    malicious_input = "db; rm -rf /"

    # Should be properly quoted
    result = cluster.run_os_command(f"echo {shell.quote(malicious_input)}")
    assert "rm -rf" not in result.text

def test_credential_not_logged():
    """Test credentials are not logged."""
    with LogCapture() as logs:
        cluster = Cluster(host="localhost", password="secret")

    # Password should not appear in logs
    assert "secret" not in str(logs)
```

## Security Checklist

Before deploying or releasing:

- [ ] All SQL queries use parameterization or SQL composition
- [ ] All shell commands use proper quoting
- [ ] No credentials in code or logs
- [ ] SSL/TLS enabled for production connections
- [ ] Input validation on all user-provided data
- [ ] Least privilege principle applied
- [ ] Audit logging for security events
- [ ] Rate limiting implemented
- [ ] Dependencies pinned and audited
- [ ] Security tests passing
- [ ] Code review completed
- [ ] Penetration testing performed (for production)
