SELECT
  p.oid AS oid
, p.proname AS name
, s.nspname AS schema
, r.rolname AS owner
, l.lanname AS language
, CASE
    WHEN p.proisagg THEN 'a'
    WHEN p.proiswindow THEN 'w'
    ELSE 'f'
  END AS kind
, p.prosecdef AS security_definer
, p.proleakproof AS leak_proof
, p.proisstrict AS strict
, p.provolatile AS volatility
, p.proparallel AS parallel_mode
, (SELECT array_agg(t.typname)
    FROM unnest(p.proargtypes) WITH ORDINALITY as args(oid)
    JOIN pg_type t ON args.oid = t.oid
) AS argument_types
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace s ON p.pronamespace = s.oid
JOIN pg_catalog.pg_roles r on p.proowner = r.oid
JOIN pg_language l on l.oid = p.prolang
WHERE s.nspname <> 'pg_catalog'
