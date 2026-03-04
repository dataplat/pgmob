SELECT
  datname AS name
, r.rolname AS owner
, pg_encoding_to_char(d.encoding) AS encoding
, d.datcollate AS collation
, d.datctype AS character_type
, d.datistemplate AS is_template
, d.datallowconn AS allow_connections
, d.datconnlimit AS connection_limit
, d.datlastsysoid AS last_sys_oid
, d.datfrozenxid AS frozen_xid
, d.datminmxid AS min_multixact_id
, t.spcname AS tablespace
, d.datacl AS acl
, d.oid AS oid
FROM pg_catalog.pg_database d
JOIN pg_catalog.pg_roles r on d.datdba = r.oid
JOIN pg_catalog.pg_tablespace t on t.oid = d.dattablespace
