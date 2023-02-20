Managed Objects
===============

Before trying any of the code below, connect to the cluster by running:

.. code:: python

    from pgmob import Cluster
    cluster = Cluster(host="127.0.0.1", user="postgres", password="s3cur3p@ss")

Databases
^^^^^^^^^

Database objects are managing PostgreSQL databases. Even though we can only see a list of
objects from the database we are currently connected to, Cluster object provides an
interface to databases regardless of the currently active database.

.. code:: python

    ### creating. modifying, and dropping databases
    db = cluster.databases.new(database="mydb", template="mytemplatedb", owner="myuser", is_template=True)
    cluster.databases.add(db)
    cluster.databases["mydb"].name = "mynewdbname"
    cluster.databases["mydb"].alter()
    cluster.databases.refresh()
    cluster.databases["mynewdbname"].drop()
    ### working with database collection
    foo_db = cluster.databases.new(database="foo")
    foo_db.create()
    dir(foo_db)
    for db in cluster.databases:
        print(db.name, db.is_template)
    if foo_db.name in cluster.databases:
        foo_db.disable()
    sql = foo_db.script().replace("foo", "bar")
    cluster.execute(sql)

.. autoclass:: pgmob.objects.Database
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.DatabaseCollection
  :members:


Roles
^^^^^

Role objects represent PostgreSQL roles (or users). It is a classic Managed Object that can be created, scripted, modified,
and dropped.

.. code:: python

    ### creating, modifying, and dropping roles
    cluster.roles.new(name="myrole", password="mypassword", superuser=True, replication=True, login=False, connection_limit=20).create()
    cluster.roles.refresh()
    cluster.roles["myrole"].change_password("mynewpassword")
    cluster.roles["myrole"].superuser = False
    cluster.roles["myrole"].replication = False
    cluster.roles["myrole"].login = True
    cluster.roles["myrole"].connection_limit = -1
    cluster.roles["myrole"].alter()
    cluster.roles["myrole"].drop()
    ### working with role collection
    dir(cluster.roles["somerole"])
    for role in cluster.roles:
        print(role.name, role.login)
    if "somerole" in cluster.roles:
        sql = cluster.roles["somerole"].script()
        cluster.execute(sql.replace("somerole", "newrole"))

.. autoclass:: pgmob.objects.Role
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.RoleCollection
  :members:

Replication Slots
^^^^^^^^^^^^^^^^^

You can create, drop, and disconnect replication slots by interacting with the Replication Slot collection.

.. code:: python

    ### create and delete replication slots
    cluster.replication_slots.new(name='slotname', plugin='pglogical').create()
    cluster.replication_slots.refresh()
    cluster.replication_slots["slotname"].drop()
    ### working with slot collection
    dir(cluster.replication_slots["myslot"])
    for slot in cluster.replication_slots:
        print(slot.name, slot.is_active)
    if "myslot" in cluster.replication_slots:
        cluster.replication_slots["myslot"].disconnect()

.. autoclass:: pgmob.objects.ReplicationSlot
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.ReplicationSlotCollection
  :members:

Tables
^^^^^^

You can perform simple maintainance operations with tables, such as renaming and changing schema and/or ownership.

.. code:: python

    dir(cluster.tables["mytable"])
    for tbl in cluster.tables:
        print(tbl.name, tbl.schema)
    # modify an Managed Object
    tbl = cluster.tables["userschema.mytable"]
    tbl.owner = "newowner"
    ### push changes to PostgreSQL
    tbl.apply()
    ### refresh object attributes from server
    tbl = cluster.tables["mytable"]
    tbl.owner = "newowner"
    tbl.refresh()  # reverts the attributes to their original values
    assert tbl.owner == "oldowner"
    ### other methods
    if "mytable" in cluster.tables:
        cluster.tables["mytable"].drop(cascade=True)

.. autoclass:: pgmob.objects.Table
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.TableCollection
  :members:

Views
^^^^^

You can perform simple maintainance operations with views, such as renaming and changing schema and/or ownership.

.. code:: python

    dir(cluster.views["mytable"])
    for v in cluster.views:
        print(v.name, v.schema)
    # modify an Managed Object
    v = cluster.views["userschema.myview"]
    v.owner = "newowner"
    ### push changes to PostgreSQL
    v.apply()
    ### refresh object attributes from server
    v = cluster.views["mytable"]
    v.owner = "newowner"
    v.refresh()  # reverts the attributes to their original values
    assert v.owner == "oldowner"
    ### other methods
    if "myview" in cluster.views:
        cluster.views["myview"].drop(cascade=True)

.. autoclass:: pgmob.objects.View
  :members:

.. autoclass:: pgmob.objects.ViewCollection
  :members:

Sequences
^^^^^^^^^

.. code:: python

    dir(cluster.sequences["table_id_seq"])
    ### interact with sequence values
    seq = cluster.sequences["table_id_seq"]
    print(seq.nextval())
    print(seq.currval())
    seq.setval(12345)
    seq.drop()

.. autoclass:: pgmob.objects.Sequence
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.SequenceCollection
  :members:

Procedures and Functions
^^^^^^^^^^^^^^^^^^^^^^^^

All of the programmable objects such as Functions or Procedures are stored in the ``procedures`` attribute of the Cluster
object. PostgreSQL can uniquely identify such procedures by a combination of name and its arguments. When accessing the index
of a ``procedures`` attribute, we would first get a ``ProcedureVariations`` list, which, in turn, contains individual
procedure objects.

.. code:: python

    dir(cluster.procedures["myfunc"][0])
    for proc in [p for procvar in cluster.procedures for p in procvar]:
        print(proc.name, proc.schema)
    # modify an Managed Object
    proc = cluster.procedures["userschema.myproc"][0]
    proc.owner = "newowner"
    ### push changes to PostgreSQL
    proc.apply()
    ### refresh object attributes from PostgreSQL
    proc = cluster.procedures["myproc"]
    proc.owner = "newowner"
    proc.refresh()  # reverts the attributes to their original values
    assert proc.owner == "oldowner"
    ### drop the procedures
    if "myfunc" in cluster.procedures:
        for pv in cluster.procedures["myfunc"]:
            pv.drop()


.. autoclass:: pgmob.objects.Procedure
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.Function
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.WindowFunction
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.Aggregate
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.ProcedureVariations
  :members:

.. autoclass:: pgmob.objects.ProcedureCollection
  :members:

Large Objects
^^^^^^^^^^^^^

Large objects are indexed by their object id.


.. code:: python

    dir(cluster.large_objects)
    for obj in cluster.large_objects:
        print(obj.id, obj.owner)
    cluster.large_objects[123].write(b'foo')
    cluster.large_objects[123].read()

.. autoclass:: pgmob.objects.LargeObject
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.LargeObjectCollection
  :members:

Schemas
^^^^^^^

Database schema management.


.. code:: python

    dir(cluster.schemas)
    for schema in cluster.schemas:
        print(schema.name, schema.owner)
    cluster.schemas["foo"].owner = "newowner"
    cluster.schemas["foo"].alter()
    cluster.schemas["foo"].drop(cascade=True)

.. autoclass:: pgmob.objects.LargeObject
  :members:
  :inherited-members:

.. autoclass:: pgmob.objects.LargeObjectCollection
  :members:


HBA Rule collection
^^^^^^^^^^^^^^^^^^^

The HBA Rule collection object represents strings in the ``pg_hba.conf`` file. After modifying the rules,
issue ``.apply()`` against the whole collection to save them to PostgreSQL. An old copy of the ``pg_hba.conf``
file will be stored under ``$PGDATA/pg_hba.conf.bak.pgm``.

HBA Rules are derived from strings, which, however, would ignore whitespace when comparing one to another.
This makes it convenient to modify the HBA rules using the simple syntax, similarly how you would add a list
to a string array:

.. code:: python

    hba = cluster.hba_rules
    print(hba)
    for rule in hba:
        print(rule)
    hba.append("local postgres postgres trust")
    hba.remove("local    postgres   postgres   trust")
    rule = "local any postgres trust"
    if rule not in hba:
      hba.insert(1, rule)
    ### push changes to PostgreSQL
    hba.apply()

.. autoclass:: pgmob.objects.HBARule
  :members:

.. autoclass:: pgmob.objects.HBARuleCollection
  :members:
