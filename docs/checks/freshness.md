# Freshness

Purpose: ensure the latest timestamp on a side is within an acceptable lag.

How it works (`src/checks/freshness.py`):

- Renders base query for the selected side (`'on': source|target`)
- Computes `MAX(<timestamp_column>)`
- Normalizes to UTC and compares with current UTC time
- PASS if `lag_minutes <= max_lag_minutes`

Config fields

- `type: freshness`
- `column` (or `col`) — required
- `'on': source|target` — default `source`  [YAML: quote the key `'on'`]
- `max_lag_minutes` — required

Examples

```
- type: freshness
  'on': target
  column: last_updated_at
  max_lag_minutes: 60

- type: freshness
  'on': source
  col: updated_at
  max_lag_minutes: 15
```

Details output

```
details: {
  on, column, latest, now_utc, lag_minutes, max_lag_minutes
}
```

Timezone & type handling

- Connectors may return native datetime types or strings; the check normalizes to UTC.
- If a naive datetime is returned, it is treated as UTC.
- For string timestamps, ISO‑8601 is parsed; invalid strings result in a best‑effort fallback.

Notes

- Always quote `'on'` in YAML. See Reference → YAML Quoting Rules.

