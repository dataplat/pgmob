SELECT
  t.tablename
, t.tableowner
, t.schemaname
, t.tablespace
, t.rowsecurity
, c.oid
FROM pg_catalog.pg_tables t
JOIN pg_catalog.pg_namespace n ON n.nspname = t.schemaname
JOIN pg_catalog.pg_class c ON n.oid = c.relnamespace AND t.tablename = c.relname