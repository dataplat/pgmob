PGMob - PostgreSQL Managed Objects
==================================

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


Example code
------------

.. code-block:: python

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


Installing
----------

PGMob requires an adapter to talk to PostgreSQL, which it can detect automatically. Currently supported adapters:

* psycopg2

To install the module without an adapter (you would have to download it by other means) use

.. code-block:: shell

    $ pip install -U pgmob


To include the adapter, use pip extras feature:

.. code-block:: shell

    $ pip install -U pgmob[psycopg2]


Documentation
-------------

.. toctree::
  :maxdepth: 2

  pgmob/cluster
  pgmob/backup
  pgmob/objects
  pgmob/sql
  pgmob/util
  pgmob/errors
  pgmob/adapters


Cluster object
~~~~~~~~~~~~~~

Cluster object is your starting point of using PGMob. It establishes and maintains a connection to a PostgreSQL server
and contains collections of asynchronous objects that help you build the blocks of automation using unified approach.
Provide the connection information in the class constructor. The class constructor will accept any and all connection
parameters supported by the underlying connection adapter, such as `psycopg2`.

.. code:: python

    from pgmob import Cluster

    # connecting to a cluster as postgres
    cluster = Cluster(host='localhost', user='postgres')
    cluster.execute('SELECT a from table')

    # connecting to a specific database
    cluster = Cluster(user='mydbadmin', password='sup3rsec@re', dbname='mydb')
    cluster.execute('SELECT a from table')


Managed Objects
~~~~~~~~~~~~~~~

Most of the Python objects in PGMob are asynchronously connected to the corresponding object on a remote PostgreSQL server.
By changing their state via setting attribute values, you prepare and, eventually, push the changes to the remote.
Such objects are called "Managed Objects".

It is assumed that the provided connection credentials have all the required permissions to modify the objects on the
remote server. Generally, we recommend to use SUPERUSER privileges when working with the module.

.. code:: python

    cluster = Cluster(user='postgres')

Managed objects can only be retrieved from the current connection context. To access objects from a different database,
you need to connect to that database by adding a ``database`` argument to the Cluster object initialization.

The majority of Managed object collections are lazy-evaluated: they will be retrieved upon accessing them, and, subsequently, cached.
To refresh the list of cached objects issue a ``.refresh()`` method of the collection:

.. code:: python

    cluster.tables.refresh()  # refresh table objects
    # or
    cluster.refresh()  # refresh all managed objects


GCP bucket backup/restore
^^^^^^^^^^^^^^^^^^^^^^^^^

GCP backups require postgres OS user to have access to gsutil commands
that allow connectivity with GCP environments. The utility should be
authenticated in GCP to work.

During the restore, the database backup is copied from the bucket to the local disk before restore.
You can customize the temporary folder using the ``temp_path`` argument of the GCPRestore class.

Similarly to file backups, GCP objects provide an option to specify a ``bucket``
to work with, which would be treated as a default path prefix.

.. code:: python

    from pgmob.backup import GCPBackup, GCPRestore
    ### backup database foo
    backup = GCPBackup(cluster=cluster)
    backup.options.no_privileges = True
    backup.options.schemas = ["public"]
    backup.backup(database="foo", path="gs://tmp/foo")
    ### restore two tables into database bar using 4 parallel jobs and disregarding tablespaces
    restore = GCPRestore(cluster=cluster, bucket="gs://tmp/")
    restore.options.no_tablespaces = True
    restore.options.tables = ["a", "b"]
    restore.options.jobs = 4
    restore.restore(database="bar", path="foo")
