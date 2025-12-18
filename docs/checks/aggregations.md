# Aggregations

Purpose: compare aggregate metrics across the entire source/target selections. `count` and `distinct_count` rules can detect specific mismatched IDs when values differ.

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

Method semantics

- `count` — column optional (`*` if omitted)
- `distinct_count` — requires a column (or both `source_column` and `target_column`)
- `sum`, `avg`, `min`, `max` — require column(s)

Datetime tolerance

- When comparing datetime results (e.g., `min`, `max`), `tolerance_abs` is interpreted as minutes (parsed to UTC and diffed in minutes).

ID Column Resolution

For `count` and `distinct_count` rules, the ID column for mismatch detection uses a comprehensive fallback chain:

1. `rule.id_column_source` / `rule.id_column_target` (highest priority)
2. `check.id_column_source` / `check.id_column_target`
3. `rule.id_column` / `check.id_column`
4. `rule.source_column` / `rule.target_column` (the aggregation column itself)
5. `rule.column` / `rule.col`
6. `check.column` / `check.col` (lowest priority)

This allows specifying just `column` in a rule and having it work for both aggregation and mismatch ID detection.

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
# Simple aggregations with tolerance
- type: aggregations
  tolerance_abs: 10
  tolerance_pct: 1.0
  rules:
    - method: count
    - method: sum
      column: amount
    - method: max
      source_column: LAST_UPDATED_AT
      target_column: last_updated_at
      tolerance_abs: 5   # minutes for datetime

# Count with mismatch IDs using column fallback
- type: aggregations
  tolerance_pct: 0.1
  rules:
    - method: count
      column: order_id  # Used for both COUNT and ID detection
    - method: distinct_count
      column: customer_id

# Different source/target columns
- type: aggregations
  rules:
    - method: distinct_count
      source_column: person_id
      target_column: PERSON_ID

# Explicit ID columns
- type: aggregations
  id_column_source: RECORD_ID
  id_column_target: record_id
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
      # Mismatch IDs fields (when enabled):
      mismatch_ids_summary?,
      missing_in_target_count?, extra_in_target_count?,
      has_extra_in_target?, mismatch_ids_csv_uri? }
  ]
}
```

Notes

- Use `order_by` when source/target subqueries need deterministic ordering for engine constraints.
- Pre-cast numeric/date types when needed to keep comparisons consistent.
- When `results_storage.mismatch_ids.enabled` is true, count-based rules detect and export specific mismatched IDs.
- Alerts display difference percentage for each failed rule (e.g., "aggregations[count] (diff: 2.3%)").
- When `extra_in_target` is detected, alerts show a critical warning section.
