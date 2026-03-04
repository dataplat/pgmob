SELECT
  t.tablename AS name
, t.tableowner AS owner
, t.schemaname AS schema
, t.tablespace AS tablespace
, t.rowsecurity AS row_security
, c.oid AS oid
FROM pg_catalog.pg_tables t
JOIN pg_catalog.pg_namespace n ON n.nspname = t.schemaname
JOIN pg_catalog.pg_class c ON n.oid = c.relnamespace AND t.tablename = c.relname
