SELECT
  s.sequencename
, s.sequenceowner
, s.schemaname
, s.data_type
, s.start_value
, s.min_value
, s.max_value
, s.increment_by
, s.cycle
, s.cache_size
, s.last_value
, c.oid
FROM pg_catalog.pg_sequences s
JOIN pg_catalog.pg_namespace n ON n.nspname = s.schemaname
JOIN pg_catalog.pg_class c ON n.oid = c.relnamespace AND s.sequencename = c.relname