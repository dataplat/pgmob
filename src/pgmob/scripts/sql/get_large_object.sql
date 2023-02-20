select
  lo.oid
, r.rolname as lomowner
FROM pg_largeobject_metadata lo
JOIN pg_catalog.pg_roles r on lo.lomowner = r.oid