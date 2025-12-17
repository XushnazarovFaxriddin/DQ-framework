# Row Count

Purpose: compare row counts between source and target selections and, when they differ, surface where the gap sits via range sampling and CSV export.

How it works (`src/checks/row_count.py`):

- Renders base `SELECT` for source/target via connectors.
- Wraps into `SELECT COUNT(*) FROM (<base>)` (with optional deterministic `ORDER BY`).
- Compares integers for equality.
- If counts differ and `mismatch_sampling` is configured, scans ID ranges (chunk or binary) to highlight where the delta lives and optionally exports a CSV.

Config fields

- `type: row_count`
- `id_column` (or `id_column_source` / `id_column_target`): numeric ID used for range sampling.
- `mismatch_sampling` (optional): drive range-based diagnosis when counts diverge.
  - `mode: chunk | binary`
  - `chunk_size`: slice size for chunk mode
  - `max_scan_chunks`, `max_ranges`: limits to bound work
  - `max_depth`: recursion depth for binary mode
- Ordering options (optional):
  - `order_by: [ canonical cols ]` mapped via `table.column_map` to each side
  - `order_by_source: [ raw exprs ]` overrides for source
  - `order_by_target: [ raw exprs ]` overrides for target

Examples

```yaml
# Simple count
- type: row_count

# Deterministic ordering
- type: row_count
  order_by: [id]

# Range sampling with chunk mode (best for wide IDs)
- type: row_count
  id_column: RECORD_ID
  mismatch_sampling:
    mode: chunk
    chunk_size: 200000
    max_scan_chunks: 50

# Binary sampling (recursively narrows hotspots)
- type: row_count
  id_column_source: RECORD_ID
  id_column_target: record_id
  mismatch_sampling:
    mode: binary
    max_depth: 6
    max_scan_chunks: 40
```

Details output

```
details: {
  source_count: <int>,
  target_count: <int>,
  config_summary: { id, sample_mode, chunk_size? },
  mismatch_ranges: [ {range_start, range_end, source_count, target_count, diff}, ... ],
  mismatch_csv_uri: <uri>,
  mismatch_csv_uris: [<uri>, ...]
}
```

Status

- PASS if counts equal; otherwise FAIL.
- When mismatch sampling runs, alerts show only summary stats and a CSV link (no huge JSON dumps).
