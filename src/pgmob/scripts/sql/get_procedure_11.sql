SELECT
  p.oid
, p.proname
, s.nspname as schemaname
, r.rolname as proowner
, l.lanname as prolang
, p.prokind
, p.prosecdef
, p.proleakproof
, p.proisstrict
, p.provolatile
, p.proparallel
, (SELECT array_agg(t.typname)
    FROM unnest(p.proargtypes) WITH ORDINALITY as args(oid)
    JOIN pg_type t ON args.oid = t.oid
) as proargtypes
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace s ON p.pronamespace = s.oid
JOIN pg_catalog.pg_roles r on p.proowner = r.oid
JOIN pg_language l on l.oid = p.prolang
WHERE s.nspname <> 'pg_catalog'