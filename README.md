![CI](https://github.com/dataplat/pgmob/actions/workflows/CI.yaml/badge.svg)
# PGMob - PostgreSQL Management Objects

PGMob is a Python package that helps to simplify PostgreSQL administration by providing a layer of abstraction that allows you
to write simple and easily understandable code instead of having to rely on SQL syntax. It's your one tool that helps you to
manage your PostgreSQL clusters on any scale and automate routine operations with ease.

PGMob abstracts away the complexity of SQL code and presents a user with a easy to use interface that controls most of
the aspects of PostgreSQL administration. It will ensure you won't have to switch between Python and SQL while building
automation tasks and it will guide you through the process with type helpers and examples.

With PGMob, you can:

* Control your server while having access to only PostgreSQL protocol
* Ensure users, databases, and database objects define as you want them
* Execute backup/restore operations on your server without having to remember the command syntax
* Script and export your database objects on the fly


## Installing

PGMob requires an adapter to talk to PostgreSQL, which it can detect automatically. Currently supported adapters:

* psycopg2

To install the module without an adapter (you would have to download it by other means) use

```shell
$ pip install -U pgmob
```

To include the adapter, use pip extras feature:

```shell
$ pip install -U pgmob[psycopg2]
```

## Documentation

TBD

## Example code

```python
from pgmob import Cluster

cluster = Cluster(host="127.0.0.1", user="postgres", password="s3cur3p@ss")

# Execute a simple query with parameters
cluster.execute("SELECT tableowner FROM pg_tables WHERE tablename LIKE %s", "pg*")

# Create a new database owner and reassign ownership
owner_role = cluster.roles.new(name="db1owner", password="foobar")
owner_role.create()
db = cluster.databases["db1"]
db.owner = owner_role.name
db.alter()

# Modify pg_hba on the fly:
entry = "host all all 127.0.0.1/32 trust"
if entry not in cluster.hba_rules:
    cluster.hba_rules.extend(entry)
    cluster.hba_rules.alter()

# clone an existing role
sql = cluster.roles["somerole"].script()
cluster.execute(sql.replace("somerole", "newrole"))

# control access to your database
cluster.terminate(databases=["somedb"], roles=["someapp"])
cluster.databases["someotherdb"].disable()

# run backups/restores
from pgmob.backup import FileBackup, FileRestore

file_backup = FileBackup(cluster=cluster)
file_backup.options.schema_only = True
file_backup.backup(database="db1", path="/tmp/db.bak")

cluster.databases.new("db2").create()
file_restore = FileRestore(cluster=cluster)
file_restore.restore(database="db2", path="/tmp/db.bak")

# create, modify, and drop objects
cluster.schemas.new("app_schema").create()
for t in [t for t in cluster.tables if t.schema == "old_schema"]:
    t.schema = "app_schema"
    t.alter()
cluster.schemas["old_schema"].drop()
```

## Dynamic objects and collections

Each Python object in PGMob is asynchronously connected to the corresponding object on the server. When changing object attributes,
one only changes the local object. In order to push the changes to the server, one needs to execute the `.alter()` method of the dynamic
object solidyfing the changes on the server.

When working with collections, such as tables, procedures, and others, you can retrieve corresponding objects using their name as index:

```python
cluster.tables["tablename"]
# or, in case the schema is not public
cluster.tables["myschema.tablename"]
```

However, you can iterate upon such collections as if they were a list:

```python
for t in cluster.tables:
    t.owner = "new_owner"
    t.alter()
if "myschema.tab1" in cluster.tables:
    cluster.tables["myschema.tab1"].drop()
```

This helps the developer to write a concise and readable code when working with PostgreSQL objects.

## Links

TBD
