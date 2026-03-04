SELECT
  rolname AS name
, rolsuper AS superuser
, rolinherit AS inherit
, rolcreaterole AS createrole
, rolcreatedb AS createdb
, rolcanlogin AS login
, rolreplication AS replication
, rolconnlimit AS connection_limit
, rolvaliduntil AS valid_until
, rolbypassrls AS bypassrls
, oid AS oid
FROM pg_catalog.pg_roles
