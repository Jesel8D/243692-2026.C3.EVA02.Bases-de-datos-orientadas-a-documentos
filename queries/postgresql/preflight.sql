SELECT json_build_object(
  'count', (SELECT count(*) FROM public.orders),
  'order_types', (SELECT coalesce(json_agg(t),'[]'::json) FROM (
    SELECT jsonb_typeof(data->'timestamp') AS timestamp,
           jsonb_typeof(data->'payment'->'final_total') AS final_total,
           jsonb_typeof(data->'payment'->'totals'->'final_total') AS totals_final_total,
           jsonb_typeof(data->'payment'->'status') AS status,
           jsonb_typeof(data->'order_id') AS order_id,
           jsonb_typeof(data->'customer'->'id') AS customer_id, count(*) AS n
    FROM public.orders GROUP BY 1,2,3,4,5,6) t),
  'item_types', (SELECT coalesce(json_agg(t),'[]'::json) FROM (
    SELECT jsonb_typeof(item->'qty') AS qty, jsonb_typeof(item->'price') AS price, count(*) AS n
    FROM public.orders, jsonb_array_elements(data->'items') item GROUP BY 1,2) t),
  'invalid_qty', (SELECT count(*) FROM public.orders, jsonb_array_elements(data->'items') item
    WHERE (item->>'qty') IS NULL OR (item->>'qty') !~ '^[1-6]$'),
  'invalid_timestamps', (SELECT count(*) FROM public.orders WHERE NOT coalesce(
    CASE WHEN jsonb_typeof(data->'timestamp')='string' AND
      data->>'timestamp' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'
    THEN to_char((data->>'timestamp')::timestamptz AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"Z"')=data->>'timestamp'
    ELSE false END, false)),
  'invalid_alias', (SELECT count(*) FROM public.orders
    WHERE data->'payment'->'final_total' IS DISTINCT FROM data->'payment'->'totals'->'final_total')
);
