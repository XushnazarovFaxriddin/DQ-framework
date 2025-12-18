# Row Count

Purpose: compare row counts between source and target selections and, when they differ, surface where the gap sits via range sampling, ID detection, and CSV export.

How it works (`src/checks/row_count.py`):

- Renders base `SELECT` for source/target via connectors.
- Wraps into `SELECT COUNT(*) FROM (<base>)` (with optional deterministic `ORDER BY`).
- Compares integers for equality.
- If counts differ and `mismatch_sampling` is configured, scans ID ranges (chunk or binary) to highlight where the delta lives and optionally exports a CSV.
- If counts differ and `mismatch_ids` is enabled, detects specific IDs that are missing or extra in target.

Config fields

- `type: row_count`
- `id_column` (or `id_column_source` / `id_column_target`): numeric ID used for range sampling and mismatch ID detection.
- `mismatch_sampling` (optional): drive range-based diagnosis when counts diverge.
  - `mode: chunk | binary`
  - `chunk_size`: slice size for chunk mode
  - `max_scan_chunks`, `max_ranges`: limits to bound work
  - `max_depth`: recursion depth for binary mode
- Ordering options (optional):
  - `order_by: [ canonical cols ]` mapped via `table.column_map` to each side
  - `order_by_source: [ raw exprs ]` overrides for source
  - `order_by_target: [ raw exprs ]` overrides for target

Mismatch IDs Detection

When row counts differ, DQF can detect the specific IDs that are:
- **Missing in target**: IDs that exist in source but not in target
- **Extra in target**: IDs that exist in target but not in source (critical data integrity issue!)

Configuration via `results_storage.mismatch_ids`:
- `enabled`: enable/disable detection (default from `DQF_MISMATCH_IDS_ENABLED`)
- `path_template`: CSV path format (default: `{config_file}/{check_name}/{table_name}-{date}.csv`)
- `chunk_size`: IDs per comparison chunk (default from `DQF_MISMATCH_IDS_CHUNK_SIZE`, recommended: 500000)
- `max_ids`: maximum IDs to export (default from `DQF_MISMATCH_IDS_MAX_IDS`)
- `separate_files`: create separate CSV files for missing vs extra IDs

CSV files include dashboard-ready metadata:
- `id`: the mismatched ID value
- `mismatch_type`: `missing_in_target` or `extra_in_target`
- `table_name`, `check_name`, `config_file`
- `detection_timestamp` (EST timezone)

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

# With mismatch IDs detection for specific ID export
- type: row_count
  id_column_source: RECORD_ID
  id_column_target: record_id
  mismatch_sampling:
    mode: binary
    max_depth: 8
    chunk_size: 500000
```

Results Storage Configuration

```yaml
results_storage:
  mismatch_ids:
    enabled: true
    path_template: "{config_file}/{check_name}/{table_name}-{date}.csv"
    chunk_size: 500000
    max_ids: 100000
    separate_files: false
```

Details output

```
details: {
  source_count: <int>,
  target_count: <int>,
  config_summary: { id, sample_mode, chunk_size? },
  mismatch_ranges: [ {range_start, range_end, source_count, target_count, diff}, ... ],
  mismatch_csv_uri: <uri>,
  mismatch_csv_uris: [<uri>, ...],
  # Mismatch IDs fields (when enabled):
  missing_in_target_count: <int>,
  extra_in_target_count: <int>,
  has_extra_in_target: <bool>,  # Critical flag for alerts
  mismatch_ids_csv_uri: <uri>,
  extra_in_target_csv_uri: <uri>  # Separate file when separate_files=true
}
```

Status

- PASS if counts equal; otherwise FAIL.
- When mismatch sampling runs, alerts show only summary stats and a CSV link (no huge JSON dumps).
- When `extra_in_target` is detected, alerts show a critical warning section.
