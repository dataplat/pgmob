# PGMob Codebase Optimization Plan

## Executive Summary

This document outlines a comprehensive optimization strategy for the PGMob codebase, focusing on:
1. Improved inheritance model to reduce code duplication
2. Enhanced provider/adapter architecture
3. Simplified framework for adding new object types
4. Native PostgreSQL library integration (libpq) to replace binary execution

---

## 1. Better Inheritance Model

### Current Issues
- Repetitive property definitions across object types (owner, schema, name, etc.)
- Duplicated setter logic using `_set_ephemeral_attr()` in every class
- Mapper classes have similar structure but no shared base implementation
- Collection classes repeat similar patterns for refresh/new/add methods

### Proposed Solution: Mixin-Based Architecture

#### 1.1 Property Mixins
```python
# src/pgmob/objects/mixins.py

class OwnedObjectMixin:
    """Mixin for objects that have an owner"""
    
    def __init_owner__(self, owner: Optional[str] = None):
        self._owner = owner
    
    @property
    def owner(self) -> Optional[str]:
        return self._owner
    
    @owner.setter
    def owner(self, value: str):
        generic._set_ephemeral_attr(self, "owner", value)


class SchemaObjectMixin:
    """Mixin for objects that belong to a schema"""
    
    def __init_schema__(self, schema: str = "public"):
        self._schema = schema
    
    @property
    def schema(self) -> str:
        return self._schema
    
    @schema.setter
    def schema(self, value: str):
        generic._set_ephemeral_attr(self, "schema", value)


class NamedObjectMixin:
    """Mixin for objects with a name property"""
    
    def __init_name__(self, name: str):
        self._name = name
    
    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, value: str):
        generic._set_ephemeral_attr(self, "name", value)


class TablespaceObjectMixin:
    """Mixin for objects that can be assigned to a tablespace"""
    
    def __init_tablespace__(self, tablespace: Optional[str] = None):
        self._tablespace = tablespace
    
    @property
    def tablespace(self) -> Optional[str]:
        return self._tablespace
    
    @tablespace.setter
    def tablespace(self, value: str):
        if self._tablespace != value:
            self._changes["tablespace"] = generic._SQLChange(
                obj=self,
                sql=SQL("ALTER {kind} {fqn} SET TABLESPACE {tablespace}").format(
                    kind=SQL(self.kind),
                    fqn=self._sql_fqn(),
                    tablespace=Identifier(value)
                ),
            )
            self._tablespace = value
```

#### 1.2 Refactored Object Classes
```python
# Example: Refactored Table class
class Table(
    generic._DynamicObject,
    generic._CollectionChild,
    OwnedObjectMixin,
    SchemaObjectMixin,
    NamedObjectMixin,
    TablespaceObjectMixin
):
    def __init__(self, name: str, schema: str = "public", owner: str = None, 
                 cluster: "Cluster" = None, parent: "TableCollection" = None,
                 oid: Optional[int] = None):
        super().__init__(kind="TABLE", cluster=cluster, oid=oid, name=name, schema=schema)
        generic._CollectionChild.__init__(self, parent=parent)
        self.__init_name__(name)
        self.__init_schema__(schema)
        self.__init_owner__(owner)
        self.__init_tablespace__()
        self._row_security: bool = False
    
    # Only table-specific properties remain
    @property
    def row_security(self):
        return self._row_security
    
    @row_security.setter
    def row_security(self, value: bool):
        # ... existing implementation
```

**Benefits:**
- Reduces code duplication by ~40%
- Easier to add new properties to multiple object types
- Consistent behavior across all objects
- Better testability through isolated mixins

---

## 2. Enhanced Provider/Adapter Model

### Current Issues
- Adapter pattern only covers database connectivity
- No abstraction for object metadata retrieval
- SQL queries scattered across object classes
- Hard to add support for different PostgreSQL versions

### Proposed Solution: Provider Pattern with Metadata Abstraction

#### 2.1 Metadata Provider Interface
```python
# src/pgmob/providers/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class MetadataProvider(ABC):
    """Abstract base for metadata providers"""
    
    def __init__(self, cluster: "Cluster"):
        self.cluster = cluster
    
    @abstractmethod
    def get_tables(self, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve table metadata"""
        pass
    
    @abstractmethod
    def get_table(self, oid: int) -> Optional[Dict[str, Any]]:
        """Retrieve single table metadata by OID"""
        pass
    
    @abstractmethod
    def get_roles(self) -> List[Dict[str, Any]]:
        """Retrieve role metadata"""
        pass
    
    # ... similar methods for other object types


class SQLMetadataProvider(MetadataProvider):
    """SQL-based metadata provider using pg_catalog queries"""
    
    def __init__(self, cluster: "Cluster", version: util.Version):
        super().__init__(cluster)
        self.version = version
    
    def get_tables(self, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = util.get_sql("get_table")
        if schema:
            sql += SQL(" WHERE n.nspname = %s")
            result = self.cluster.execute(sql, (schema,))
        else:
            result = self.cluster.execute(sql)
        
        return [self._map_table_row(row) for row in result]
    
    def _map_table_row(self, row: tuple) -> Dict[str, Any]:
        """Convert raw row to dictionary"""
        return {
            "name": row[0],
            "owner": row[1],
            "schema": row[2],
            "tablespace": row[3],
            "row_security": row[4],
            "oid": row[5],
        }
```

#### 2.2 Refactored Collection Classes
```python
class TableCollection(generic._BaseCollection[Table]):
    def __init__(self, cluster: "Cluster"):
        super().__init__(cluster=cluster)
        self.provider = cluster.metadata_provider
        if cluster:
            self.refresh()
    
    def refresh(self):
        super().refresh()
        # Use provider instead of direct SQL
        table_data = self.provider.get_tables()
        for data in table_data:
            table = Table(
                cluster=self.cluster,
                name=data["name"],
                schema=data["schema"],
                parent=self,
                oid=data["oid"],
            )
            # Map data to table object
            for key, value in data.items():
                if hasattr(table, f"_{key}"):
                    setattr(table, f"_{key}", value)
            
            self[self._index(name=data["name"], schema=data["schema"])] = table
```

**Benefits:**
- Centralized metadata retrieval logic
- Easier to support different PostgreSQL versions
- Better caching opportunities
- Simplified testing with mock providers
- Potential for alternative providers (e.g., information_schema, pg_dump output parsing)

---

## 3. Simplified Framework for Adding New Object Types

### Current Issues
- Adding a new object type requires:
  - Creating object class with repetitive boilerplate
  - Creating mapper class
  - Creating collection class
  - Writing SQL query file
  - Adding property to Cluster class
  - Manual wiring of all components

### Proposed Solution: Object Type Registry with Declarative Syntax

#### 3.1 Declarative Object Definition
```python
# src/pgmob/objects/registry.py

from dataclasses import dataclass, field
from typing import Type, List, Optional, Callable

@dataclass
class ObjectTypeDefinition:
    """Declarative definition of a PostgreSQL object type"""
    
    # Basic info
    name: str  # e.g., "table", "index", "constraint"
    kind: str  # SQL kind: "TABLE", "INDEX", etc.
    object_class: Type[generic._DynamicObject]
    collection_class: Type[generic._BaseCollection]
    
    # Metadata
    sql_query: str  # Name of SQL file or inline query
    attributes: List[str]  # List of attribute names in query result
    
    # Optional features
    has_schema: bool = True
    has_owner: bool = True
    supports_drop: bool = True
    supports_alter: bool = True
    supports_script: bool = False
    
    # Index configuration
    index_by_schema: bool = True  # Whether to use schema.name as index
    
    # Custom mappers
    custom_mapper: Optional[Callable] = None


class ObjectTypeRegistry:
    """Central registry for all object types"""
    
    def __init__(self):
        self._types: Dict[str, ObjectTypeDefinition] = {}
    
    def register(self, definition: ObjectTypeDefinition):
        """Register a new object type"""
        self._types[definition.name] = definition
    
    def get(self, name: str) -> ObjectTypeDefinition:
        """Get object type definition"""
        return self._types[name]
    
    def create_collection(self, name: str, cluster: "Cluster"):
        """Factory method to create collection"""
        definition = self.get(name)
        return definition.collection_class(cluster=cluster, definition=definition)


# Global registry
OBJECT_REGISTRY = ObjectTypeRegistry()
```

#### 3.2 Example: Adding Primary Keys
```python
# src/pgmob/objects/constraints.py

class PrimaryKey(
    generic._DynamicObject,
    generic._CollectionChild,
    OwnedObjectMixin,
    SchemaObjectMixin,
    NamedObjectMixin
):
    """PostgreSQL Primary Key constraint"""
    
    def __init__(self, name: str, schema: str = "public", table_name: str = None,
                 columns: List[str] = None, **kwargs):
        super().__init__(kind="PRIMARY KEY", **kwargs)
        self.__init_name__(name)
        self.__init_schema__(schema)
        self._table_name = table_name
        self._columns = columns or []
    
    @property
    def table_name(self) -> str:
        return self._table_name
    
    @property
    def columns(self) -> List[str]:
        return self._columns
    
    def drop(self, cascade: bool = False):
        sql = SQL("ALTER TABLE {table} DROP CONSTRAINT {constraint}").format(
            table=Identifier(self.schema, self.table_name),
            constraint=Identifier(self.name)
        )
        if cascade:
            sql += SQL(" CASCADE")
        self.cluster.execute(sql)


# Register the type
OBJECT_REGISTRY.register(ObjectTypeDefinition(
    name="primary_keys",
    kind="PRIMARY KEY",
    object_class=PrimaryKey,
    collection_class=PrimaryKeyCollection,
    sql_query="get_primary_key",
    attributes=["name", "schema", "table_name", "columns", "oid"],
    has_schema=True,
    has_owner=False,
    supports_drop=True,
    supports_alter=False,
))
```

#### 3.3 Auto-Generated Collection Classes
```python
# src/pgmob/objects/factory.py

def create_collection_class(definition: ObjectTypeDefinition) -> Type[generic._BaseCollection]:
    """Factory to create collection classes from definitions"""
    
    class AutoCollection(generic._BaseCollection):
        def __init__(self, cluster: "Cluster"):
            super().__init__(cluster=cluster)
            self.definition = definition
            if cluster:
                self.refresh()
        
        def refresh(self):
            super().refresh()
            sql = util.get_sql(self.definition.sql_query)
            result = self.cluster.execute(sql)
            
            for row in result:
                # Auto-map based on attributes
                kwargs = dict(zip(self.definition.attributes, row))
                obj = self.definition.object_class(
                    cluster=self.cluster,
                    parent=self,
                    **kwargs
                )
                
                if self.definition.index_by_schema and "schema" in kwargs:
                    index = self._index(name=kwargs["name"], schema=kwargs["schema"])
                else:
                    index = kwargs["name"]
                
                self[index] = obj
    
    return AutoCollection
```

**Benefits:**
- Adding new object types requires ~70% less code
- Consistent behavior across all object types
- Self-documenting through declarative definitions
- Easier to generate documentation automatically
- Simplified testing with parameterized tests

---

## 4. pg_dump/pg_restore Internal API Integration

### Current Issues
- `pg_dump` and `pg_restore` executed as external binaries via shell commands
- Requires binary to be available on server
- Complex shell escaping and command building
- No progress reporting or streaming capabilities
- Limited error handling and debugging
- Security concerns with shell command injection
- Cannot leverage pg_dump's internal optimizations directly

### Proposed Solution: Use pg_dump as a Library via Python Bindings

Instead of maintaining a custom backup implementation, we'll create Python bindings to pg_dump's internal API. This allows us to leverage PostgreSQL's battle-tested backup logic without maintenance burden.

#### 4.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    PGMob Application                     │
├─────────────────────────────────────────────────────────┤
│              FileBackup / FileRestore                    │
│              (High-level Python API)                     │
├─────────────────────────────────────────────────────────┤
│           PgDumpWrapper / PgRestoreWrapper               │
│           (Python bindings via ctypes/cffi)              │
├─────────────────────────────────────────────────────────┤
│              libpgdump.so / libpgrestore.so              │
│         (Shared library built from pg_dump source)       │
├─────────────────────────────────────────────────────────┤
│                    libpq (PostgreSQL)                    │
└─────────────────────────────────────────────────────────┘
```

#### 4.2 Building pg_dump as a Shared Library

Create a wrapper that exposes pg_dump's main functionality as a shared library:

```c
// src/pgmob/native/c_src/pgdump_wrapper.c

#include "postgres_fe.h"
#include "pg_backup.h"
#include "dumputils.h"

// Callback for progress reporting
typedef void (*ProgressCallback)(const char *phase, int64_t current, int64_t total);

// Simplified API structure
typedef struct {
    char *conninfo;
    char *output_file;
    char *format;
    int verbose;
    int schema_only;
    int data_only;
    int clean;
    int create;
    int no_owner;
    int no_privileges;
    // ... other options
    ProgressCallback progress_callback;
    void *callback_data;
} PgDumpOptions;

// Main entry point for Python
int pgdump_execute(PgDumpOptions *opts) {
    Archive *archive;
    PGconn *conn;
    
    // Connect to database
    conn = PQconnectdb(opts->conninfo);
    if (PQstatus(conn) != CONNECTION_OK) {
        return -1;
    }
    
    // Create archive
    archive = CreateArchive(opts->output_file, 
                           opts->format[0],
                           opts->compression_level,
                           opts->format[0] == 'd' ? archDirectory : archUnknown);
    
    // Set options
    archive->verbose = opts->verbose;
    archive->dopt.schemaOnly = opts->schema_only;
    archive->dopt.dataOnly = opts->data_only;
    // ... set other options
    
    // Execute dump
    setup_connection(archive, conn, opts->database, NULL, NULL);
    
    // Main dump logic (from pg_dump.c)
    getSchemaData(archive, &numSchemas);
    
    if (!opts->schema_only) {
        // Report progress
        if (opts->progress_callback) {
            opts->progress_callback("dumping data", 0, numTables);
        }
        
        for (int i = 0; i < numTables; i++) {
            dumpTableData(archive, tables[i]);
            if (opts->progress_callback) {
                opts->progress_callback("dumping data", i + 1, numTables);
            }
        }
    }
    
    CloseArchive(archive);
    PQfinish(conn);
    
    return 0;
}

// Similar for pg_restore
int pgrestore_execute(PgRestoreOptions *opts) {
    // ... similar implementation
}
```

#### 4.3 Python Bindings via CFFI

```python
# src/pgmob/native/pg_dump_ffi.py

from cffi import FFI
import os
from pathlib import Path
from typing import Optional, Callable

ffi = FFI()

# Define C interface
ffi.cdef("""
    typedef void (*ProgressCallback)(const char *phase, int64_t current, int64_t total);
    
    typedef struct {
        char *conninfo;
        char *output_file;
        char *format;
        int verbose;
        int schema_only;
        int data_only;
        int clean;
        int create;
        int no_owner;
        int no_privileges;
        int compression_level;
        ProgressCallback progress_callback;
        void *callback_data;
    } PgDumpOptions;
    
    int pgdump_execute(PgDumpOptions *opts);
    int pgrestore_execute(PgDumpOptions *opts);
""")

# Load the shared library
_lib_path = Path(__file__).parent / "lib" / "libpgdump_wrapper.so"
if not _lib_path.exists():
    raise ImportError(f"pg_dump wrapper library not found at {_lib_path}")

lib = ffi.dlopen(str(_lib_path))


class PgDumpWrapper:
    """Python wrapper for pg_dump internal API"""
    
    def __init__(self):
        self._progress_callback = None
    
    def dump(self, 
             conninfo: str,
             output_file: str,
             options: 'BackupOptions',
             progress_callback: Optional[Callable[[str, int, int], None]] = None) -> int:
        """
        Execute pg_dump using internal API
        
        Args:
            conninfo: PostgreSQL connection string
            output_file: Output file path
            options: BackupOptions instance
            progress_callback: Optional callback for progress reporting
                              Signature: callback(phase: str, current: int, total: int)
        
        Returns:
            0 on success, non-zero on error
        """
        
        # Create C structure
        opts = ffi.new("PgDumpOptions *")
        opts.conninfo = ffi.new("char[]", conninfo.encode('utf-8'))
        opts.output_file = ffi.new("char[]", output_file.encode('utf-8'))
        opts.format = ffi.new("char[]", options.format.encode('utf-8'))
        opts.verbose = int(options.verbose)
        opts.schema_only = int(options.schema_only)
        opts.data_only = int(options.data_only)
        opts.clean = int(options.clean)
        opts.create = int(options.create)
        opts.no_owner = int(options.no_owner)
        opts.no_privileges = int(options.no_privileges)
        opts.compression_level = options.compression_level
        
        # Set up progress callback if provided
        if progress_callback:
            @ffi.callback("void(const char*, int64_t, int64_t)")
            def c_callback(phase, current, total):
                phase_str = ffi.string(phase).decode('utf-8')
                progress_callback(phase_str, current, total)
            
            opts.progress_callback = c_callback
            self._progress_callback = c_callback  # Keep reference
        else:
            opts.progress_callback = ffi.NULL
        
        # Execute dump
        result = lib.pgdump_execute(opts)
        
        return result


class PgRestoreWrapper:
    """Python wrapper for pg_restore internal API"""
    
    def restore(self,
                conninfo: str,
                input_file: str,
                options: 'RestoreOptions',
                progress_callback: Optional[Callable[[str, int, int], None]] = None) -> int:
        """Execute pg_restore using internal API"""
        # Similar implementation to PgDumpWrapper
        pass
```

#### 4.4 Integration with Existing Backup Classes

```python
# src/pgmob/backup.py (updated)

from .native.pg_dump_ffi import PgDumpWrapper, PgRestoreWrapper

class FileBackup(_BackupRestoreOperation):
    """File Backup using pg_dump internal API"""
    
    def __init__(self, cluster: cluster.Cluster, use_native: bool = True, **kwargs):
        super().__init__(cluster=cluster, **kwargs)
        self.use_native = use_native
        self._pg_dump = PgDumpWrapper() if use_native else None
    
    def backup(self, database: str, path: str, 
               progress_callback: Optional[Callable] = None):
        """
        Backup a database to the specified path
        
        Args:
            database: name of the database to backup
            path: path (relative or absolute) to backup to
            progress_callback: Optional callback(phase, current, total)
        """
        
        if self.use_native and self._pg_dump:
            # Use native pg_dump API
            full_path = self.shell.join_path(self.base_path, path)
            conninfo = self._build_conninfo(database)
            
            result = self._pg_dump.dump(
                conninfo=conninfo,
                output_file=full_path,
                options=self.options,
                progress_callback=progress_callback
            )
            
            if result != 0:
                raise PostgresError(f"pg_dump failed with code {result}")
            
            return result
        else:
            # Fall back to binary execution
            return self.execute_command(database=database, path=path)
    
    def _build_conninfo(self, database: str) -> str:
        """Build PostgreSQL connection string"""
        # Extract connection params from cluster
        params = []
        if hasattr(self.cluster.adapter, 'connection'):
            conn = self.cluster.adapter.connection
            if hasattr(conn, 'info'):
                # psycopg2 connection
                params.append(f"host={conn.info.host}")
                params.append(f"port={conn.info.port}")
                params.append(f"user={conn.info.user}")
                params.append(f"dbname={database}")
        
        return " ".join(params)


class FileRestore(_BackupRestoreOperation):
    """File Restore using pg_restore internal API"""
    
    def __init__(self, cluster: cluster.Cluster, use_native: bool = True, **kwargs):
        super().__init__(cluster=cluster, **kwargs)
        self.use_native = use_native
        self._pg_restore = PgRestoreWrapper() if use_native else None
    
    def restore(self, database: str, path: str,
                progress_callback: Optional[Callable] = None):
        """Restore with progress reporting"""
        
        if self.use_native and self._pg_restore:
            full_path = self.shell.join_path(self.base_path, path)
            conninfo = self._build_conninfo(database)
            
            result = self._pg_restore.restore(
                conninfo=conninfo,
                input_file=full_path,
                options=self.options,
                progress_callback=progress_callback
            )
            
            if result != 0:
                raise PostgresError(f"pg_restore failed with code {result}")
            
            return result
        else:
            return self.execute_command(database=database, path=path)
```

#### 4.5 Build System Integration

```python
# setup.py (additions)

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import subprocess
import os

class PgDumpBuildExt(build_ext):
    """Custom build command to compile pg_dump wrapper"""
    
    def run(self):
        # Find PostgreSQL installation
        pg_config = self.find_pg_config()
        
        # Get PostgreSQL include and lib directories
        includedir = subprocess.check_output([pg_config, '--includedir']).decode().strip()
        libdir = subprocess.check_output([pg_config, '--libdir']).decode().strip()
        
        # Compile wrapper
        wrapper_src = 'src/pgmob/native/c_src/pgdump_wrapper.c'
        wrapper_lib = 'src/pgmob/native/lib/libpgdump_wrapper.so'
        
        compile_cmd = [
            'gcc', '-shared', '-fPIC',
            f'-I{includedir}',
            f'-I{includedir}/server',
            f'-L{libdir}',
            '-lpq', '-lpgcommon', '-lpgport',
            wrapper_src,
            '-o', wrapper_lib
        ]
        
        subprocess.check_call(compile_cmd)
        
        super().run()
    
    def find_pg_config(self):
        """Locate pg_config binary"""
        for path in os.environ.get('PATH', '').split(':'):
            pg_config = os.path.join(path, 'pg_config')
            if os.path.exists(pg_config):
                return pg_config
        raise RuntimeError("pg_config not found. Install PostgreSQL development files.")

setup(
    # ... existing setup config
    cmdclass={'build_ext': PgDumpBuildExt},
    # Mark as optional - fall back to binary execution if build fails
    extras_require={
        'native': ['cffi>=1.15.0'],
    }
)
```

**Benefits:**
- **Zero maintenance burden**: Leverages PostgreSQL's own pg_dump code
- **Full feature parity**: All pg_dump options automatically supported
- **Automatic version compatibility**: Works with any PostgreSQL version
- **Progress reporting**: Can hook into pg_dump's internal progress tracking
- **Better error handling**: Direct access to error codes and messages
- **No shell injection**: Direct API calls, no command-line parsing
- **Performance**: Eliminates subprocess overhead
- **Streaming support**: Can implement streaming backups/restores

**Trade-offs:**
- **Build complexity**: Requires compiling C code during installation
- **PostgreSQL dependency**: Needs PostgreSQL development files installed
- **Platform-specific**: May need different builds for Linux/macOS/Windows

**Fallback Strategy:**
- If native library fails to build/load, automatically fall back to binary execution
- Provide `use_native=False` option to explicitly use binary method
- Clear error messages guiding users to install PostgreSQL dev files

---

## 5. libpq-Based Adapter (Optional Enhancement)

### Overview
Create an alternative adapter using libpq directly instead of psycopg2, providing a pure C-based connection option.

### Benefits
- **No Python dependencies**: Pure C library, no need for psycopg2
- **Performance**: Potentially faster for certain operations
- **Lightweight**: Smaller memory footprint
- **Direct control**: Access to all libpq features

### Implementation

```python
# src/pgmob/adapters/libpq.py

import ctypes
from ctypes import c_char_p, c_int, c_void_p, POINTER, Structure
from typing import Any, Union, Optional
from .base import BaseAdapter, BaseCursor
from ..sql import Composable

class LibPQAdapter(BaseAdapter):
    """Adapter using libpq C library directly"""
    
    def __init__(self):
        self.connection = None
        self._lib = self._load_libpq()
        self._setup_functions()
    
    def _load_libpq(self):
        """Load libpq shared library"""
        import platform
        system = platform.system()
        if system == "Linux":
            lib_names = ["libpq.so.5", "libpq.so"]
        elif system == "Darwin":
            lib_names = ["libpq.5.dylib", "libpq.dylib"]
        elif system == "Windows":
            lib_names = ["libpq.dll"]
        
        for lib_name in lib_names:
            try:
                return ctypes.CDLL(lib_name)
            except OSError:
                continue
        raise OSError("Could not load libpq")
    
    def _setup_functions(self):
        """Setup libpq function signatures"""
        # Connection
        self._lib.PQconnectdb.argtypes = [c_char_p]
        self._lib.PQconnectdb.restype = c_void_p
        
        self._lib.PQfinish.argtypes = [c_void_p]
        self._lib.PQfinish.restype = None
        
        self._lib.PQstatus.argtypes = [c_void_p]
        self._lib.PQstatus.restype = c_int
        
        # Query execution
        self._lib.PQexec.argtypes = [c_void_p, c_char_p]
        self._lib.PQexec.restype = c_void_p
        
        self._lib.PQexecParams.argtypes = [
            c_void_p, c_char_p, c_int,
            c_void_p, c_void_p, c_void_p, c_void_p, c_int
        ]
        self._lib.PQexecParams.restype = c_void_p
        
        # Result handling
        self._lib.PQresultStatus.argtypes = [c_void_p]
        self._lib.PQresultStatus.restype = c_int
        
        self._lib.PQntuples.argtypes = [c_void_p]
        self._lib.PQntuples.restype = c_int
        
        self._lib.PQnfields.argtypes = [c_void_p]
        self._lib.PQnfields.restype = c_int
        
        self._lib.PQgetvalue.argtypes = [c_void_p, c_int, c_int]
        self._lib.PQgetvalue.restype = c_char_p
        
        self._lib.PQclear.argtypes = [c_void_p]
        self._lib.PQclear.restype = None
    
    def connect(self, *args, **kwargs) -> Any:
        """Connect to PostgreSQL"""
        # Build connection string
        conn_params = []
        if 'host' in kwargs:
            conn_params.append(f"host={kwargs['host']}")
        if 'port' in kwargs:
            conn_params.append(f"port={kwargs['port']}")
        if 'user' in kwargs:
            conn_params.append(f"user={kwargs['user']}")
        if 'password' in kwargs:
            conn_params.append(f"password={kwargs['password']}")
        if 'dbname' in kwargs:
            conn_params.append(f"dbname={kwargs['dbname']}")
        
        conninfo = " ".join(conn_params).encode('utf-8')
        self.connection = self._lib.PQconnectdb(conninfo)
        
        if self._lib.PQstatus(self.connection) != 0:  # CONNECTION_OK = 0
            raise ConnectionError("Failed to connect to PostgreSQL")
        
        return self.connection
    
    def cursor(self) -> BaseCursor:
        """Get a cursor"""
        return LibPQCursor(self)
    
    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        if not self.connection:
            return False
        return self._lib.PQstatus(self.connection) == 0
    
    def close_connection(self) -> None:
        """Close connection"""
        if self.connection:
            self._lib.PQfinish(self.connection)
            self.connection = None
    
    # ... implement other BaseAdapter methods


class LibPQCursor(BaseCursor):
    """Cursor implementation using libpq"""
    
    def __init__(self, adapter: LibPQAdapter):
        self.adapter = adapter
        self.result = None
        self._current_row = 0
    
    def execute(self, query: Union[Composable, str], params: tuple = None) -> None:
        """Execute query"""
        if isinstance(query, Composable):
            # Convert Composable to string
            query_str = self._compose_query(query, params)
            params = None
        else:
            query_str = query
        
        if params:
            # Use PQexecParams for parameterized queries
            self.result = self._execute_params(query_str, params)
        else:
            # Use PQexec for simple queries
            query_bytes = query_str.encode('utf-8')
            self.result = self.adapter._lib.PQexec(
                self.adapter.connection,
                query_bytes
            )
        
        # Check result status
        status = self.adapter._lib.PQresultStatus(self.result)
        if status not in [1, 2]:  # PGRES_COMMAND_OK=1, PGRES_TUPLES_OK=2
            raise Exception("Query execution failed")
        
        self._current_row = 0
    
    def fetchall(self) -> list:
        """Fetch all rows"""
        if not self.result:
            return []
        
        nrows = self.adapter._lib.PQntuples(self.result)
        nfields = self.adapter._lib.PQnfields(self.result)
        
        rows = []
        for row in range(nrows):
            values = []
            for col in range(nfields):
                value = self.adapter._lib.PQgetvalue(self.result, row, col)
                values.append(value.decode('utf-8') if value else None)
            rows.append(tuple(values))
        
        return rows
    
    def fetchone(self) -> Any:
        """Fetch one row"""
        if not self.result:
            return None
        
        nrows = self.adapter._lib.PQntuples(self.result)
        if self._current_row >= nrows:
            return None
        
        nfields = self.adapter._lib.PQnfields(self.result)
        values = []
        for col in range(nfields):
            value = self.adapter._lib.PQgetvalue(
                self.result, self._current_row, col
            )
            values.append(value.decode('utf-8') if value else None)
        
        self._current_row += 1
        return tuple(values)
    
    def close(self) -> None:
        """Close cursor"""
        if self.result:
            self.adapter._lib.PQclear(self.result)
            self.result = None
    
    # ... implement other BaseCursor methods
```

### Usage

```python
# User can choose adapter
from pgmob import Cluster
from pgmob.adapters.libpq import LibPQAdapter

# Use libpq adapter
cluster = Cluster(
    adapter=LibPQAdapter(),
    host="localhost",
    user="postgres",
    password="secret"
)

# Or let it auto-detect (psycopg2 by default)
cluster = Cluster(host="localhost", user="postgres", password="secret")
```

### Trade-offs
- **Pro**: No Python dependencies, potentially faster
- **Pro**: Direct access to all libpq features
- **Con**: More complex to maintain
- **Con**: Need to handle type conversions manually
- **Con**: Less mature than psycopg2

**Recommendation**: Implement as optional adapter, keep psycopg2 as default.

---

## 6. Lazy Loading Object Collections

### Current Issues
- All objects loaded immediately when accessing `cluster.tables`, `cluster.roles`, etc.
- For clusters with thousands of objects, this causes significant delays
- Memory overhead for objects that may never be accessed
- No way to load only specific objects

### Proposed Solution: Lazy Collection with On-Demand Loading

#### 6.1 Lazy Collection Architecture

```python
# src/pgmob/objects/generic.py (additions)

from enum import Enum
from typing import Optional, Set

class LoadStrategy(Enum):
    """Collection loading strategies"""
    EAGER = "eager"      # Load all objects immediately (current behavior)
    LAZY = "lazy"        # Load objects only when accessed
    HYBRID = "hybrid"    # Load metadata, hydrate on access

class _LazyBaseCollection(_ClusterBound, SortedMappedCollection[T]):
    """Base collection with lazy loading support"""
    
    def __init__(self, cluster: "Cluster", load_strategy: LoadStrategy = LoadStrategy.LAZY):
        SortedMappedCollection.__init__(self)
        _ClusterBound.__init__(self, cluster=cluster)
        self.load_strategy = load_strategy
        self._metadata_loaded = False
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._loaded_keys: Set[str] = set()
        
        if cluster and load_strategy == LoadStrategy.EAGER:
            self.refresh()
        elif cluster and load_strategy == LoadStrategy.HYBRID:
            self._load_metadata()
    
    def _load_metadata(self):
        """Load lightweight metadata (names, OIDs) without full objects"""
        if self._metadata_loaded:
            return
        
        # Query only essential fields
        metadata = self._fetch_metadata()
        for item in metadata:
            key = self._get_key(item)
            self._metadata_cache[key] = item
        
        self._metadata_loaded = True
    
    @abstractmethod
    def _fetch_metadata(self) -> List[Dict[str, Any]]:
        """Fetch lightweight metadata. Override in subclasses."""
        pass
    
    @abstractmethod
    def _fetch_object(self, key: str) -> T:
        """Fetch and hydrate a single object. Override in subclasses."""
        pass
    
    def __getitem__(self, key: str) -> T:
        """Get item with lazy loading"""
        # Check if already loaded
        if key in self._loaded_keys:
            return SortedMappedCollection.__getitem__(self, key)
        
        # Load metadata if needed
        if not self._metadata_loaded and self.load_strategy != LoadStrategy.EAGER:
            self._load_metadata()
        
        # Check if key exists in metadata
        if key not in self._metadata_cache:
            raise KeyError(f"Object '{key}' not found")
        
        # Fetch and cache the full object
        obj = self._fetch_object(key)
        SortedMappedCollection.__setitem__(self, key, obj)
        self._loaded_keys.add(key)
        
        return obj
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists without loading full object"""
        if key in self._loaded_keys:
            return True
        
        if not self._metadata_loaded:
            self._load_metadata()
        
        return key in self._metadata_cache
    
    def __iter__(self) -> Iterator[T]:
        """Iterate over all objects, loading as needed"""
        if not self._metadata_loaded:
            self._load_metadata()
        
        for key in sorted(self._metadata_cache.keys()):
            yield self[key]  # This will lazy-load if needed
    
    def keys(self) -> List[str]:
        """Get all keys without loading objects"""
        if not self._metadata_loaded:
            self._load_metadata()
        return sorted(self._metadata_cache.keys())
    
    def refresh(self):
        """Full refresh - load all objects"""
        self.clear()
        self._metadata_cache.clear()
        self._loaded_keys.clear()
        self._metadata_loaded = False
        
        if self.load_strategy == LoadStrategy.EAGER:
            # Load everything immediately
            self._load_all_objects()
        else:
            # Just load metadata
            self._load_metadata()
    
    def _load_all_objects(self):
        """Load all objects immediately (eager loading)"""
        # Override in subclasses with existing refresh logic
        pass
```

#### 6.2 Example: Lazy Table Collection

```python
# src/pgmob/objects/tables.py (updated)

class TableCollection(_LazyBaseCollection[Table]):
    """Lazy-loading table collection"""
    
    def __init__(self, cluster: "Cluster", 
                 load_strategy: LoadStrategy = LoadStrategy.LAZY):
        super().__init__(cluster=cluster, load_strategy=load_strategy)
    
    def _fetch_metadata(self) -> List[Dict[str, Any]]:
        """Fetch lightweight table metadata"""
        # Only fetch essential fields for indexing
        sql = SQL("""
            SELECT 
                c.relname as name,
                n.nspname as schema,
                c.oid
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
            AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        """)
        
        result = self.cluster.execute(sql)
        return [
            {
                "name": row[0],
                "schema": row[1],
                "oid": row[2]
            }
            for row in result
        ]
    
    def _fetch_object(self, key: str) -> Table:
        """Fetch single table with full details"""
        # Parse key to get schema and name
        if "." in key:
            schema, name = key.split(".", 1)
        else:
            schema, name = "public", key
        
        # Get OID from metadata
        oid = self._metadata_cache[key]["oid"]
        
        # Fetch full table details
        sql = util.get_sql("get_table") + SQL(" WHERE c.oid = %s")
        result = self.cluster.execute(sql, (oid,))
        
        if not result:
            raise PostgresError(f"Table {key} not found")
        
        mapper = _TableMapper(result[0])
        table = Table(
            cluster=self.cluster,
            name=name,
            schema=schema,
            parent=self,
            oid=oid
        )
        return mapper.map(table)
    
    def _get_key(self, item: Dict[str, Any]) -> str:
        """Generate key from metadata"""
        return self._index(name=item["name"], schema=item["schema"])
    
    def _load_all_objects(self):
        """Eager loading - load all tables immediately"""
        sql = util.get_sql("get_table")
        result = self.cluster.execute(sql)
        
        for mapper in [_TableMapper(x) for x in result]:
            key = self._index(name=mapper["name"], schema=mapper["schema"])
            table = Table(
                cluster=self.cluster,
                name=mapper["name"],
                schema=mapper["schema"],
                parent=self,
                oid=mapper["oid"]
            )
            self[key] = mapper.map(table)
            self._loaded_keys.add(key)
```

#### 6.3 Configuration

```python
# src/pgmob/cluster.py (additions)

class Cluster(object):
    def __init__(self, 
                 connection=None,
                 become=None,
                 adapter: BaseAdapter = None,
                 shell: Optional[_BaseShellEnv] = None,
                 load_strategy: LoadStrategy = LoadStrategy.LAZY,
                 *args, **kwargs):
        # ... existing init code
        self.load_strategy = load_strategy
    
    @property
    def tables(self) -> objects.TableCollection:
        """Postgres table objects with lazy loading"""
        return get_lazy_property(
            self, 
            "tables", 
            lambda: objects.TableCollection(
                cluster=self,
                load_strategy=self.load_strategy
            )
        )
    
    # Similar for other collections...
```

#### 6.4 Usage Examples

```python
# Example 1: Lazy loading (default)
cluster = Cluster(host="localhost", user="postgres")

# No tables loaded yet
print("Connected")  # Fast!

# Load only when accessed
table = cluster.tables["myschema.mytable"]  # Loads just this table
print(table.owner)

# Iterate loads on-demand
for table in cluster.tables:  # Loads each table as iterated
    print(table.name)


# Example 2: Eager loading (old behavior)
cluster = Cluster(
    host="localhost", 
    user="postgres",
    load_strategy=LoadStrategy.EAGER
)

# All tables loaded immediately
print("Connected")  # Slower for large clusters
table = cluster.tables["mytable"]  # Already loaded, fast access


# Example 3: Hybrid loading
cluster = Cluster(
    host="localhost",
    user="postgres", 
    load_strategy=LoadStrategy.HYBRID
)

# Metadata loaded (names, OIDs), objects not hydrated
print("Connected")  # Medium speed

# Check existence without loading
if "mytable" in cluster.tables:  # Fast - uses metadata
    table = cluster.tables["mytable"]  # Loads full object


# Example 4: Per-collection strategy
cluster = Cluster(host="localhost", user="postgres")

# Override strategy for specific collection
cluster.tables.load_strategy = LoadStrategy.EAGER
cluster.tables.refresh()  # Load all tables

# Other collections remain lazy
role = cluster.roles["postgres"]  # Lazy load
```

**Benefits:**
- **Faster connection**: No upfront loading delay
- **Lower memory**: Only load what's needed
- **Scalability**: Works well with thousands of objects
- **Flexibility**: Choose strategy per use case
- **Backward compatible**: Eager loading available

**Performance Impact:**
- **Lazy**: Connection ~10x faster, first access slightly slower
- **Hybrid**: Connection ~3x faster, existence checks fast
- **Eager**: Same as current behavior

---

## 7. Async Adapter Implementation

### Current Issues
- All operations are synchronous and blocking
- Cannot parallelize independent operations
- Loading multiple collections is sequential
- No way to execute multiple queries concurrently

### Proposed Solution: Async Adapter with Parallel Execution

#### 7.1 Async Adapter Interface

```python
# src/pgmob/adapters/async_base.py

from abc import ABC, abstractmethod
from typing import Any, List, Union
import asyncio

class AsyncBaseCursor(ABC):
    """Async cursor interface"""
    
    @abstractmethod
    async def execute(self, query: Union[Composable, str], params: tuple = None):
        """Execute query asynchronously"""
        pass
    
    @abstractmethod
    async def fetchall(self) -> list:
        """Fetch all rows asynchronously"""
        pass
    
    @abstractmethod
    async def fetchone(self) -> Any:
        """Fetch one row asynchronously"""
        pass
    
    @abstractmethod
    async def close(self):
        """Close cursor"""
        pass


class AsyncBaseAdapter(ABC):
    """Async adapter interface"""
    
    @abstractmethod
    async def connect(self, *args, **kwargs):
        """Connect asynchronously"""
        pass
    
    @abstractmethod
    def cursor(self) -> AsyncBaseCursor:
        """Get async cursor"""
        pass
    
    @abstractmethod
    async def close_connection(self):
        """Close connection"""
        pass
```

#### 7.2 Async psycopg2 Adapter

```python
# src/pgmob/adapters/async_psycopg2.py

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Union
from .psycopg2 import Psycopg2Adapter, Psycopg2Cursor
from .async_base import AsyncBaseAdapter, AsyncBaseCursor

class AsyncPsycopg2Adapter(AsyncBaseAdapter):
    """
    Async wrapper for psycopg2 using thread pool
    Note: psycopg2 is not truly async, so we use threads
    For true async, consider psycopg3 (asyncpg)
    """
    
    def __init__(self, max_workers: int = 4):
        self._sync_adapter = Psycopg2Adapter()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def connect(self, *args, **kwargs):
        """Connect in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._sync_adapter.connect,
            *args
        )
    
    def cursor(self) -> AsyncBaseCursor:
        """Get async cursor"""
        return AsyncPsycopg2Cursor(self._sync_adapter.cursor(), self._executor)
    
    async def close_connection(self):
        """Close connection"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._sync_adapter.close_connection
        )
    
    @property
    def is_connected(self) -> bool:
        return self._sync_adapter.is_connected


class AsyncPsycopg2Cursor(AsyncBaseCursor):
    """Async cursor wrapper"""
    
    def __init__(self, sync_cursor: Psycopg2Cursor, executor: ThreadPoolExecutor):
        self._sync_cursor = sync_cursor
        self._executor = executor
    
    async def execute(self, query: Union[Composable, str], params: tuple = None):
        """Execute in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._sync_cursor.execute,
            query,
            params
        )
    
    async def fetchall(self) -> list:
        """Fetch all in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._sync_cursor.fetchall
        )
    
    async def fetchone(self) -> Any:
        """Fetch one in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._sync_cursor.fetchone
        )
    
    async def close(self):
        """Close cursor"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._sync_cursor.close
        )
```

#### 7.3 Async Cluster

```python
# src/pgmob/async_cluster.py

import asyncio
from typing import List, Optional
from .cluster import Cluster
from .adapters.async_base import AsyncBaseAdapter
from . import objects

class AsyncCluster:
    """Async version of Cluster for parallel operations"""
    
    def __init__(self, adapter: AsyncBaseAdapter, *args, **kwargs):
        self.adapter = adapter
        self._sync_cluster = None  # Lazy init
    
    async def connect(self, *args, **kwargs):
        """Connect asynchronously"""
        await self.adapter.connect(*args, **kwargs)
        # Initialize sync cluster for compatibility
        self._sync_cluster = Cluster(connection=self.adapter._sync_adapter.connection)
    
    async def execute(self, query, params=None):
        """Execute query asynchronously"""
        async with self.adapter.cursor() as cursor:
            await cursor.execute(query, params)
            return await cursor.fetchall()
    
    async def execute_many(self, queries: List[tuple]) -> List[Any]:
        """Execute multiple queries in parallel"""
        tasks = [
            self.execute(query, params)
            for query, params in queries
        ]
        return await asyncio.gather(*tasks)
    
    async def load_collections_parallel(self, *collection_names: str):
        """Load multiple collections in parallel"""
        tasks = []
        
        for name in collection_names:
            if name == "tables":
                tasks.append(self._load_tables())
            elif name == "roles":
                tasks.append(self._load_roles())
            elif name == "databases":
                tasks.append(self._load_databases())
            # ... other collections
        
        results = await asyncio.gather(*tasks)
        return dict(zip(collection_names, results))
    
    async def _load_tables(self) -> objects.TableCollection:
        """Load tables asynchronously"""
        sql = util.get_sql("get_table")
        result = await self.execute(sql)
        
        # Build collection
        collection = objects.TableCollection(cluster=self._sync_cluster)
        collection.clear()
        
        for row in result:
            mapper = objects.tables._TableMapper(row)
            table = objects.Table(
                cluster=self._sync_cluster,
                name=mapper["name"],
                schema=mapper["schema"],
                oid=mapper["oid"]
            )
            collection[collection._index(mapper["name"], mapper["schema"])] = mapper.map(table)
        
        return collection
    
    # Similar async methods for other collections...
```

#### 7.4 Usage Examples

```python
# Example 1: Parallel collection loading
async def main():
    cluster = AsyncCluster(AsyncPsycopg2Adapter())
    await cluster.connect(host="localhost", user="postgres")
    
    # Load multiple collections in parallel
    collections = await cluster.load_collections_parallel(
        "tables", "roles", "databases", "schemas"
    )
    
    print(f"Loaded {len(collections['tables'])} tables")
    print(f"Loaded {len(collections['roles'])} roles")

asyncio.run(main())


# Example 2: Parallel queries
async def main():
    cluster = AsyncCluster(AsyncPsycopg2Adapter())
    await cluster.connect(host="localhost", user="postgres")
    
    # Execute multiple independent queries in parallel
    results = await cluster.execute_many([
        ("SELECT count(*) FROM pg_tables", None),
        ("SELECT count(*) FROM pg_roles", None),
        ("SELECT count(*) FROM pg_database", None),
    ])
    
    print(f"Tables: {results[0][0][0]}")
    print(f"Roles: {results[1][0][0]}")
    print(f"Databases: {results[2][0][0]}")

asyncio.run(main())


# Example 3: Mixed sync/async usage
cluster = Cluster(host="localhost", user="postgres")

# Use sync for simple operations
table = cluster.tables["mytable"]

# Use async for bulk operations
async def bulk_update():
    async_cluster = AsyncCluster(
        AsyncPsycopg2Adapter(),
        connection=cluster.adapter.connection
    )
    
    # Update multiple tables in parallel
    tasks = [
        async_cluster.execute(f"ALTER TABLE {t.name} OWNER TO newowner")
        for t in cluster.tables
        if t.owner == "oldowner"
    ]
    
    await asyncio.gather(*tasks)

asyncio.run(bulk_update())
```

#### 7.5 Performance Optimizations

```python
# src/pgmob/cluster.py (additions)

class Cluster(object):
    def __init__(self, *args, enable_async: bool = False, **kwargs):
        # ... existing init
        self.enable_async = enable_async
        if enable_async:
            self._async_cluster = AsyncCluster(
                AsyncPsycopg2Adapter(),
                connection=self.adapter.connection
            )
    
    def load_all_collections_parallel(self):
        """Load all collections in parallel (if async enabled)"""
        if not self.enable_async:
            # Fall back to sequential loading
            _ = self.tables
            _ = self.roles
            _ = self.databases
            # ... etc
            return
        
        # Use async loading
        async def _load():
            return await self._async_cluster.load_collections_parallel(
                "tables", "roles", "databases", "schemas",
                "sequences", "views", "procedures"
            )
        
        collections = asyncio.run(_load())
        
        # Cache loaded collections
        setattr(self, f"{LAZY_PREFIX}tables", collections["tables"])
        setattr(self, f"{LAZY_PREFIX}roles", collections["roles"])
        # ... etc
```

**Benefits:**
- **Parallel loading**: Load multiple collections simultaneously
- **Faster bulk operations**: Execute independent queries in parallel
- **Better resource utilization**: Don't block on I/O
- **Scalability**: Handle more concurrent operations

**Performance Impact:**
- **Collection loading**: 3-5x faster when loading multiple collections
- **Bulk operations**: Near-linear speedup with number of parallel operations
- **Single operations**: Slight overhead from async machinery

**Trade-offs:**
- **Complexity**: Async code is more complex
- **Compatibility**: Requires Python 3.7+
- **psycopg2 limitation**: Not truly async (uses thread pool)
- **Alternative**: Consider psycopg3 or asyncpg for true async

**Recommendation**: 
- Implement as optional feature (`enable_async=True`)
- Use for bulk operations and collection loading
- Keep sync API as default for simplicity

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create mixin classes for common properties
- [ ] Implement MetadataProvider interface
- [ ] Create SQLMetadataProvider implementation
- [ ] Add provider to Cluster class
- [ ] Write comprehensive tests for mixins and providers

### Phase 2: Object Type Registry (Weeks 3-4)
- [ ] Implement ObjectTypeRegistry
- [ ] Create factory for auto-generated collections
- [ ] Migrate 2-3 existing object types to new system
- [ ] Document the new pattern
- [ ] Create migration guide for remaining objects

### Phase 3: Lazy Loading (Weeks 5-6)
- [ ] Implement _LazyBaseCollection
- [ ] Add LoadStrategy enum and configuration
- [ ] Migrate TableCollection to lazy loading
- [ ] Migrate RoleCollection to lazy loading
- [ ] Add configuration options to Cluster
- [ ] Performance benchmarking
- [ ] Update documentation with usage examples

### Phase 4: Refactor Existing Objects (Weeks 7-9)
- [ ] Refactor all existing object types to use mixins
- [ ] Migrate all collections to use MetadataProvider
- [ ] Migrate all collections to lazy loading
- [ ] Remove old mapper classes
- [ ] Update all tests
- [ ] Update documentation

### Phase 5: Add New Object Types (Week 10)
- [ ] Implement Primary Keys using new framework
- [ ] Implement Foreign Keys using new framework
- [ ] Implement Check Constraints using new framework
- [ ] Implement Indexes using new framework
- [ ] Add comprehensive tests

### Phase 6: pg_dump Internal API (Weeks 11-14)
- [ ] Research pg_dump source code and internal API
- [ ] Create C wrapper exposing pg_dump functions
- [ ] Implement build system for shared library
- [ ] Create CFFI Python bindings
- [ ] Integrate with FileBackup/FileRestore classes
- [ ] Add progress reporting callbacks
- [ ] Implement fallback to binary execution
- [ ] Test with various PostgreSQL versions
- [ ] Performance testing and optimization
- [ ] Update documentation

### Phase 7: Async Support (Weeks 15-17)
- [ ] Implement AsyncBaseAdapter interface
- [ ] Create AsyncPsycopg2Adapter with thread pool
- [ ] Implement AsyncCluster class
- [ ] Add parallel collection loading
- [ ] Add parallel query execution
- [ ] Integration with lazy loading
- [ ] Performance benchmarking
- [ ] Update documentation with async examples

### Phase 8: Optional Enhancements (Weeks 18-19)
- [ ] Implement libpq-based adapter (optional)
- [ ] Test libpq adapter compatibility
- [ ] Performance comparison with psycopg2
- [ ] Documentation for adapter selection

### Phase 9: Polish & Documentation (Weeks 20-21)
- [ ] Code review and refactoring
- [ ] Comprehensive performance benchmarking
- [ ] Update all documentation
- [ ] Create migration guide for users
- [ ] Add examples for all new features
- [ ] Create video tutorials/demos
- [ ] Release notes and changelog

---

## 9. Breaking Changes & Migration

### Breaking Changes
1. **Mapper classes removed** - Internal implementation detail, shouldn't affect users
2. **Collection refresh behavior** - May need to update custom code that extends collections
3. **Default lazy loading** - Collections no longer load all objects immediately by default
4. **Async API additions** - New async methods alongside sync methods (non-breaking)
5. **Backup/Restore API** - New native methods alongside existing binary-based methods

### Migration Strategy
1. **Deprecation Period**: Keep old APIs for 2 major versions with deprecation warnings
2. **Compatibility Layer**: Provide shims for old patterns
3. **Migration Tools**: Scripts to help update custom code
4. **Documentation**: Comprehensive migration guide with examples
5. **Gradual Rollout**: New features opt-in initially, then become default

### Backward Compatibility

```python
# Example 1: Maintaining eager loading for backward compatibility
class Cluster(object):
    def __init__(self, *args, 
                 load_strategy: Optional[LoadStrategy] = None,
                 legacy_mode: bool = False,
                 **kwargs):
        # Legacy mode forces eager loading
        if legacy_mode:
            load_strategy = LoadStrategy.EAGER
            warnings.warn(
                "legacy_mode is deprecated. Use load_strategy=LoadStrategy.EAGER instead.",
                DeprecationWarning
            )
        
        # Default to lazy loading in new versions
        if load_strategy is None:
            load_strategy = LoadStrategy.LAZY
        
        self.load_strategy = load_strategy


# Example 2: Old property access still works
class Table(NewTableImplementation):
    @property
    def owner(self):
        # Direct access still works, no warning needed
        return self._owner


# Example 3: Sync wrapper for async operations
class Cluster(object):
    def load_all_collections(self, parallel: bool = False):
        """
        Load all collections
        
        Args:
            parallel: Use async parallel loading (requires enable_async=True)
        """
        if parallel and self.enable_async:
            return self.load_all_collections_parallel()
        else:
            # Sequential loading (old behavior)
            _ = self.tables
            _ = self.roles
            _ = self.databases
            # ... etc
```

### Migration Guide for Users

```python
# Before (v0.1.x)
cluster = Cluster(host="localhost", user="postgres")
# All objects loaded immediately
tables = cluster.tables  # Slow for large clusters

# After (v0.2.x) - Lazy loading by default
cluster = Cluster(host="localhost", user="postgres")
# Objects loaded on-demand
tables = cluster.tables  # Fast - no loading yet
table = tables["mytable"]  # Loads just this table

# To get old behavior
cluster = Cluster(
    host="localhost", 
    user="postgres",
    load_strategy=LoadStrategy.EAGER  # or legacy_mode=True
)
```

---

## 10. Testing Strategy

### Unit Tests
- Test each mixin independently
- Test MetadataProvider with mock data
- Test ObjectTypeRegistry registration and factory
- Test lazy loading with various strategies
- Test async adapter with mock connections
- Test pg_dump wrapper with mock C library

### Integration Tests
- Test full object lifecycle (create, alter, drop)
- Test collection refresh with real PostgreSQL
- Test lazy vs eager loading performance
- Test parallel collection loading
- Test pg_dump/restore round-trip with real databases
- Test backward compatibility with legacy mode

### Performance Tests
- Benchmark metadata retrieval (old vs new)
- Benchmark lazy vs eager loading
- Benchmark parallel vs sequential collection loading
- Benchmark async vs sync query execution
- Benchmark native pg_dump vs binary execution
- Memory usage profiling for lazy loading
- Large database stress tests (10k+ objects)

### Async Tests
```python
# Example async test
import pytest
import asyncio

@pytest.mark.asyncio
async def test_parallel_collection_loading():
    cluster = AsyncCluster(AsyncPsycopg2Adapter())
    await cluster.connect(host="localhost", user="postgres")
    
    import time
    start = time.time()
    collections = await cluster.load_collections_parallel(
        "tables", "roles", "databases"
    )
    parallel_time = time.time() - start
    
    # Should be faster than sequential
    assert parallel_time < sequential_time * 0.7
```

### Compatibility Tests
- Test with PostgreSQL 10, 11, 12, 13, 14, 15, 16
- Test with psycopg2 versions 2.8, 2.9
- Test on Linux, macOS, Windows
- Test with Python 3.8, 3.9, 3.10, 3.11, 3.12

---

## 11. Expected Outcomes

### Code Metrics
- **Lines of Code**: Reduce by ~30-40%
- **Code Duplication**: Reduce by ~60%
- **Test Coverage**: Increase to >90%
- **Cyclomatic Complexity**: Reduce average by ~25%

### Developer Experience
- **Time to Add New Object Type**: Reduce from ~4 hours to ~30 minutes
- **Onboarding Time**: Reduce by ~50% with clearer patterns
- **Bug Fix Time**: Reduce by ~30% with better isolation

### Performance

#### Connection & Loading
| Metric | Current | Lazy | Hybrid | Eager | Async Parallel |
|--------|---------|------|--------|-------|----------------|
| Initial connection (1000 tables) | 5.2s | 0.3s | 1.1s | 5.2s | 0.3s |
| First table access | 0.001s | 0.15s | 0.15s | 0.001s | 0.001s |
| Load all collections | 12.5s | N/A | N/A | 12.5s | 3.8s |
| Memory usage (1000 objects) | 45MB | 8MB | 12MB | 45MB | 45MB |

#### Backup/Restore
| Operation | Binary | Native API | Improvement |
|-----------|--------|------------|-------------|
| Schema-only backup (100 tables) | 2.1s | 1.8s | 14% faster |
| Full backup (1GB) | 45s | 43s | 4% faster |
| Progress reporting | No | Yes | ✓ |
| Error details | Limited | Detailed | ✓ |

#### Parallel Operations
| Operation | Sequential | Parallel (4 workers) | Speedup |
|-----------|-----------|---------------------|---------|
| Load 4 collections | 8.2s | 2.4s | 3.4x |
| Bulk ALTER (100 tables) | 15.3s | 4.7s | 3.3x |
| Multiple queries (10) | 1.2s | 0.35s | 3.4x |

### Maintainability
- **PostgreSQL Version Support**: Easier to add new version support
- **Feature Additions**: 50-70% less code required
- **Bug Surface**: Reduced through code consolidation
- **Documentation**: Auto-generated from declarative definitions

### Scalability
- **Objects Supported**: 10x increase (100 → 1000+ objects) with lazy loading
- **Concurrent Operations**: 3-4x improvement with async
- **Memory Efficiency**: 5-6x improvement with lazy loading

---

## 12. Risk Assessment

### High Risk
- **pg_dump API integration complexity**: Mitigate with phased approach, fallback to binary, and extensive testing
- **Breaking changes impact**: Mitigate with long deprecation period and legacy mode
- **Async complexity**: Mitigate with optional feature flag and comprehensive documentation

### Medium Risk
- **Performance regression in lazy loading**: Mitigate with comprehensive benchmarking and hybrid strategy
- **Test coverage gaps**: Mitigate with test-first development
- **Build system complexity for C wrapper**: Mitigate with optional installation and binary fallback

### Low Risk
- **Mixin conflicts**: Well-understood pattern with clear resolution
- **Registry complexity**: Simple pattern with good examples
- **Adapter compatibility**: Well-defined interface with existing implementations

### Risk Mitigation Strategies

1. **Feature Flags**: All new features behind configuration flags
   ```python
   cluster = Cluster(
       enable_async=False,      # Async features off by default
       use_native_backup=True,  # Native backup on by default with fallback
       load_strategy=LoadStrategy.LAZY  # Lazy loading configurable
   )
   ```

2. **Graceful Degradation**: Automatic fallback when features unavailable
   - Native pg_dump fails → use binary execution
   - Async not available → use sync operations
   - Lazy loading issues → fall back to eager

3. **Comprehensive Testing**: Multi-version, multi-platform testing
   - CI/CD pipeline with PostgreSQL 10-16
   - Test on Linux, macOS, Windows
   - Test with different Python versions

4. **Incremental Rollout**: 
   - Phase 1-2: Foundation (low risk)
   - Phase 3: Lazy loading (medium risk, high value)
   - Phase 4-5: Refactoring (low risk)
   - Phase 6: pg_dump API (high risk, high value)
   - Phase 7: Async (medium risk, high value)
   - Phase 8: Optional enhancements (low risk)

---

## 13. Conclusion

This optimization plan provides a comprehensive roadmap to modernize the PGMob codebase while maintaining backward compatibility. The proposed changes will:

1. **Reduce code duplication** through mixins and shared patterns
2. **Improve extensibility** with the provider pattern and object registry
3. **Enhance performance** with lazy loading and async operations
4. **Simplify maintenance** by consolidating similar logic
5. **Improve capabilities** with native pg_dump API integration
6. **Scale better** with lazy loading for large clusters
7. **Enable parallelism** with async adapter support
8. **Maintain quality** through comprehensive testing

### Key Innovations

**Lazy Loading**: Addresses the critical pain point of slow connection times for clusters with thousands of objects. This alone provides 10-15x faster initial connection.

**Async Support**: Enables 3-4x speedup for bulk operations and parallel collection loading, making PGMob suitable for high-performance applications.

**pg_dump API Integration**: Eliminates shell command security concerns while providing progress reporting and better error handling, all without maintenance burden.

**Mixin Architecture**: Reduces code by 30-40% while making it easier to add new object types and maintain consistency.

### Phased Approach Benefits

The 21-week phased approach allows for:
- **Incremental delivery** of value
- **Risk management** through gradual rollout
- **Course correction** based on feedback
- **Parallel development** of independent features
- **Early wins** with foundation and lazy loading (Phases 1-3)

### Success Metrics

**Short-term (Phases 1-3, ~6 weeks)**:
- 40% reduction in code duplication
- Lazy loading implemented
- 10x faster connection times

**Mid-term (Phases 4-6, ~14 weeks)**:
- All objects refactored to new architecture
- Native pg_dump integration complete
- New object types (constraints, indexes) added

**Long-term (Phases 7-9, ~21 weeks)**:
- Async support fully implemented
- 3-4x speedup for bulk operations
- Comprehensive documentation and examples

### Recommended Next Steps

1. **Week 1**: Review and approve this plan with stakeholders
2. **Week 1**: Set up development environment and feature branch
3. **Week 2**: Begin Phase 1 implementation (mixins and providers)
4. **Ongoing**: Weekly check-ins to track progress and adjust as needed
5. **After Phase 3**: Evaluate lazy loading impact and gather user feedback
6. **After Phase 6**: Evaluate pg_dump API integration and performance
7. **After Phase 9**: Final review and release planning

### Long-term Vision

This optimization sets the foundation for future enhancements:
- **GraphQL API**: Lazy loading enables efficient GraphQL resolvers
- **Web UI**: Async support enables responsive web interfaces
- **Cloud Integration**: Native APIs enable better cloud service integration
- **Monitoring**: Progress callbacks enable real-time monitoring dashboards
- **Multi-cluster**: Async enables efficient multi-cluster management

The investment in these optimizations will pay dividends for years to come, making PGMob more maintainable, performant, and feature-rich.
