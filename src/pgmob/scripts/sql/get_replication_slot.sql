SELECT
slot_name
, plugin
, slot_type
, database
, temporary
, active
, active_pid
, xmin
, catalog_xmin
, restart_lsn
, confirmed_flush_lsn
FROM pg_catalog.pg_replication_slots