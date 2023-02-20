Backup and Restore
==================

.. automodule:: pgmob.backup

Backup/restore options
^^^^^^^^^^^^^^^^^^^^^^

Backup and restore operations are controlled by the Options object, which is available as an ``.options`` attribute
of the corresponding Backup or Restore object. Adjust settings as you would normally do in the command line, but
benefit from being able to use Python syntax.


.. autoclass:: pgmob.backup.BackupOptions
  :inherited-members:

.. autoclass:: pgmob.backup.RestoreOptions
  :inherited-members:

File backup/restore
^^^^^^^^^^^^^^^^^^^

File restore works with the files available on the PostgreSQL server. When specifying path, make sure
PostgreSQL service user (``postgres``) has access to them.

You can specify a "base" path for your backup/restore operation, making all the subsequent paths relative
to that base path.


.. autoclass:: pgmob.backup.FileBackup
  :inherited-members:

.. autoclass:: pgmob.backup.FileRestore
  :inherited-members:


GCP Bucket backup/restore
^^^^^^^^^^^^^^^^^^^^^^^^^

Similar to the File backup/restore, these classes offer to simplify restoration from a GCP Bucket. The ``postgres`` system user should
be able to use ``gs_util`` tooling to access bucket contents. During a restore operation, the database backup is copied to a temporary
location first, due to the way gs_util outputs the file into the pipeline, making it impossible to pass it to ``pg_restore``. This folder
location can be adjusted.

.. autoclass:: pgmob.backup.GCPBackup
  :inherited-members:

.. autoclass:: pgmob.backup.GCPRestore
  :inherited-members:
