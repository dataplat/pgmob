SELECT a.attname,
    format_type(a.atttypid, a.atttypmod) AS type,
    a.attstattarget,
    a.attnum,
    a.attndims > 0 as is_array,
    information_schema._pg_char_max_length(a.atttypid, a.atttypmod) AS type_mod,
    not a.attnotnull as nullable,
    a.atthasdef,
    a.attidentity,
    a.attgenerated,
    col.collname,
    pg_get_expr(d.adbin, d.adrelid) AS expr,
    CASE
        WHEN a.attidentity IN ('a','d') THEN pg_get_serial_sequence(a.attrelid::regclass::text, a.attname)
        ELSE NULL
    END as sequence_name
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
LEFT JOIN pg_catalog.pg_collation c ON c.oid = a.attcollation
LEFT JOIN pg_catalog.pg_attrdef d ON a.atthasdef AND d.adrelid = a.attrelid AND a.attnum = d.adnum
LEFT JOIN pg_catalog.pg_collation col ON a.attcollation > 0 AND col.oid = a.attcollation
WHERE a.attrelid = %s
  AND a.attnum > 0
  AND NOT a.attisdropped