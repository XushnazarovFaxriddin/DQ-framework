# Aggregations

Purpose: compare aggregate metrics across the entire source/target selections. `count` and `distinct_count` rules can optionally reuse mismatch sampling + CSV export (same as `row_count`) to locate where count gaps sit.

How it works (`src/checks/aggregations.py`):

- Renders base queries for source/target (with optional ORDER BY for determinism).
- For each rule, builds aggregate expressions on both sides.
- Fetches scalar results and compares with absolute/percentage tolerances.
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
```

Details output (expanded per rule by the markdown renderer)

```
details: {
  rules: [
    { method, column, source_column, target_column,
      source, target, tolerance_abs, tolerance_pct, pass,
      mismatch_ranges?, mismatch_csv_uri? }
  ]
}
```

Notes

- Use `order_by` when source/target subqueries need deterministic ordering for engine constraints.
- Pre-cast numeric/date types when needed to keep comparisons consistent.
- When `results_storage.mismatch_csv.enabled` is true, count-based rules attach `mismatch_csv_uri` so alerts can link to the CSV instead of inlining large payloads.
