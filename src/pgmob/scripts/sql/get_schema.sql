SELECT
  n.nspname
, r.rolname as nspowner
, n.oid
FROM pg_catalog.pg_namespace n
JOIN pg_catalog.pg_roles r on n.nspowner = r.oid