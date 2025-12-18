# Aggregations

Purpose: compare aggregate metrics across the entire source/target selections. `count` and `distinct_count` rules can optionally reuse mismatch sampling + CSV export (same as `row_count`) to locate where count gaps sit, and detect specific mismatched IDs.

How it works (`src/checks/aggregations.py`):

- Renders base queries for source/target (with optional ORDER BY for determinism).
- For each rule, builds aggregate expressions on both sides.
- Fetches scalar results and compares with absolute/percentage tolerances.
- For count-based rules with mismatches, optionally detects specific mismatched IDs.
- Overall PASS if all rules pass; otherwise FAIL.

Config fields

- `type: aggregations`
- `rules: [ {method, column|source_column|target_column, tolerance_abs, tolerance_pct}, ... ]`
- Global tolerances at check level (`tolerance_abs`, `tolerance_pct`) act as defaults.
- Ordering (optional): `order_by`, `order_by_source`, `order_by_target`.
- For `count` / `distinct_count` rules, you may add:
  - `id_column` or `id_column_source` / `id_column_target`
  - `mismatch_sampling` (chunk or binary) to compute range deltas and export CSV when mismatched.

Method semantics

- `count` — column optional (`*` if omitted)
- `distinct_count` — requires a column (or both `source_column` and `target_column`)
- `sum`, `avg`, `min`, `max` — require column(s)

Datetime tolerance

- When comparing datetime results (e.g., `min`, `max`), `tolerance_abs` is interpreted as minutes (parsed to UTC and diffed in minutes).

Mismatch IDs Detection

For `count` and `distinct_count` rules, when values differ, DQF can detect specific IDs that are:
- **Missing in target**: IDs that exist in source but not in target
- **Extra in target**: IDs that exist in target but not in source (critical data integrity issue!)

This uses the same `results_storage.mismatch_ids` configuration as `row_count`:
- `enabled`: enable/disable detection
- `path_template`: CSV path format
- `chunk_size`: IDs per comparison chunk (optimized for 10M+ rows at 500000)
- `max_ids`: maximum IDs to export
- `separate_files`: create separate files for missing vs extra

Alerts show difference percentages for each failed rule and highlight critical `extra_in_target` issues.

Examples

```yaml
- type: aggregations
  tolerance_abs: 10
  tolerance_pct: 1.0
  rules:
    - method: count
    - method: sum
      column: amount
    - method: distinct_count
      source_column: person_id
      target_column: PERSON_ID
      id_column: PERSON_ID
      mismatch_sampling:
        mode: chunk
        chunk_size: 200000
    - method: max
      source_column: LAST_UPDATED_AT
      target_column: last_updated_at
      tolerance_abs: 5   # minutes

# With mismatch IDs detection for count rules
- type: aggregations
  id_column_source: RECORD_ID
  id_column_target: record_id
  tolerance_pct: 0.1
  rules:
    - method: count
    - method: distinct_count
      source_column: customer_id
      target_column: CUSTOMER_ID
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

Details output (expanded per rule by the markdown renderer)

```
details: {
  rules: [
    { method, column, source_column, target_column,
      source, target, tolerance_abs, tolerance_pct, pass,
      mismatch_ranges?, mismatch_csv_uri?,
      # Mismatch IDs fields (when enabled):
      missing_in_target_count?, extra_in_target_count?,
      has_extra_in_target?, mismatch_ids_csv_uri? }
  ]
}
```

Notes

- Use `order_by` when source/target subqueries need deterministic ordering for engine constraints.
- Pre-cast numeric/date types when needed to keep comparisons consistent.
- When `results_storage.mismatch_csv.enabled` is true, count-based rules attach `mismatch_csv_uri` so alerts can link to the CSV instead of inlining large payloads.
- When `results_storage.mismatch_ids.enabled` is true, count-based rules detect and export specific mismatched IDs.
- Alerts display difference percentage for each failed rule (e.g., "aggregations[count] (diff: 2.3%)").
- When `extra_in_target` is detected, alerts show a critical warning section.
