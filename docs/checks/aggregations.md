# Aggregations

Purpose: compare aggregate metrics across the entire source/target selections.

How it works (`src/checks/aggregations.py`):

- Renders base queries for source/target (with optional ORDER BY for determinism)
- For each rule, builds aggregate expressions on both sides
- Fetches scalar results and compares with absolute/percentage tolerances
- Overall PASS if all rules pass

Config fields

- `type: aggregations`
- `rules: [ {method, column|source_column|target_column, tolerance_abs, tolerance_pct}, ... ]`
- Global tolerances at check level (`tolerance_abs`, `tolerance_pct`) act as defaults
- Ordering (optional): `order_by`, `order_by_source`, `order_by_target`

Method semantics

- `count` — column optional (`*` if omitted)
- `distinct_count` — requires a column (or both `source_column` and `target_column`)
- `sum`, `avg`, `min`, `max` — require column(s)

Datetime tolerance

- When comparing datetime results (e.g., `min`, `max`), `tolerance_abs` is interpreted as minutes (see code path that parses to UTC and computes minute diff).

Examples

```
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
      source, target, tolerance_abs, tolerance_pct, pass }
  ]
}
```

Notes

- Use `order_by` when source/target subqueries need deterministic ordering for engine constraints.
- Consider pre‑casting numeric/date types to ensure consistent comparisons.

