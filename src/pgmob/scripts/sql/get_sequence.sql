SELECT
  s.sequencename AS name
, s.sequenceowner AS owner
, s.schemaname AS schema
, s.data_type AS data_type
, s.start_value AS start_value
, s.min_value AS min_value
, s.max_value AS max_value
, s.increment_by AS increment_by
, s.cycle AS cycle
, s.cache_size AS cache_size
, s.last_value AS last_value
, c.oid AS oid
FROM pg_catalog.pg_sequences s
JOIN pg_catalog.pg_namespace n ON n.nspname = s.schemaname
JOIN pg_catalog.pg_class c ON n.oid = c.relnamespace AND s.sequencename = c.relname
