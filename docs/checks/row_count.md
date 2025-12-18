# Row Count

Purpose: compare row counts between source and target selections and, when they differ, detect specific mismatched IDs and export to CSV.

How it works (`src/checks/row_count.py`):

- Renders base `SELECT` for source/target via connectors.
- Wraps into `SELECT COUNT(*) FROM (<base>)` (with optional deterministic `ORDER BY`).
- Compares integers for equality.
- If counts differ and `mismatch_ids` is enabled, detects specific IDs that are missing or extra in target.

Config fields

- `type: row_count`
- `id_column` (or `id_column_source` / `id_column_target`): ID column used for mismatch detection.
  - Fallback chain: `id_column_source/target` → `id_column` → `column/col`
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

The detection algorithm automatically chooses between:
- **Chunked mode**: Sequential chunk comparison, best for small to medium ID ranges
- **Binary mode**: Recursive binary search, best for large sparse mismatches (>10M IDs)

CSV files include dashboard-ready metadata:
- `id`: the mismatched ID value
- `mismatch_type`: `missing_in_target` or `extra_in_target`
- `table_name`, `check_name`, `config_file`
- `detection_timestamp` (EST timezone)
- `is_critical`: true for extra_in_target records

Examples

```yaml
# Simple count (no mismatch ID export)
- type: row_count

# With mismatch IDs detection
- type: row_count
  id_column: RECORD_ID

# Different ID columns on source/target
- type: row_count
  id_column_source: RECORD_ID
  id_column_target: record_id

# Using column as ID fallback
- type: row_count
  column: order_id
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
  config_summary: { id },
  # Mismatch IDs fields (when enabled):
  mismatch_ids_summary: {
    source_count, target_count,
    missing_in_target_count, extra_in_target_count,
    scan_method, chunks_scanned, processing_time_ms
  },
  has_extra_in_target: <bool>,  # Critical flag for alerts
  extra_in_target_count: <int>,
  mismatch_ids_csv_uri: <uri>,
  extra_in_target_csv_uri: <uri>  # When separate_files=true
}
```

Status

- PASS if counts equal; otherwise FAIL.
- When `extra_in_target` is detected, alerts show a critical warning section.
- Difference percentage is displayed in alerts for failed checks.
