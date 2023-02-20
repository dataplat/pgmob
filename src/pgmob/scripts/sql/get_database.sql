SELECT
datname
, r.rolname as datowner
, pg_encoding_to_char(d.encoding) as encoding
, d.datcollate
, d.datctype
, d.datistemplate
, d.datallowconn
, d.datconnlimit
, d.datlastsysoid
, d.datfrozenxid
, d.datminmxid
, t.spcname as tablespace
, d.datacl
, d.oid
FROM pg_catalog.pg_database d
JOIN pg_catalog.pg_roles r on d.datdba = r.oid
JOIN pg_catalog.pg_tablespace t on t.oid = d.dattablespace