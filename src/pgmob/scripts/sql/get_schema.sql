SELECT
  n.nspname AS name
, r.rolname AS owner
, n.oid AS oid
FROM pg_catalog.pg_namespace n
JOIN pg_catalog.pg_roles r on n.nspowner = r.oid
