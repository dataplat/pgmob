SELECT
  v.viewname AS name
, v.viewowner AS owner
, v.schemaname AS schema
, c.oid AS oid
FROM pg_catalog.pg_views v
JOIN pg_catalog.pg_namespace n ON n.nspname = v.schemaname
JOIN pg_catalog.pg_class c ON n.oid = c.relnamespace AND v.viewname = c.relname
