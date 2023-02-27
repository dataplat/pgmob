SELECT a.attname,
    format_type(a.atttypid, a.atttypmod) AS type,
    a.attgenerated,
    a.atthasdef,
    a.attidentity,
    pg_get_expr(d.adbin, d.adrelid) AS expr
FROM pg_attribute a
JOIN pg_type t ON t.oid = a.atttypid
LEFT JOIN pg_collation c ON c.oid = a.attcollation
LEFT JOIN pg_attrdef d ON a.atthasdef AND d.adrelid = a.attrelid AND a.attnum = d.adnum
WHERE a.attrelid = %s::regclass
  AND a.attnum > 0
  AND NOT a.attisdropped