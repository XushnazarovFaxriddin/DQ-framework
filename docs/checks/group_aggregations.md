# Group Aggregations

Purpose: compare aggregates per partition key (group‑by) between source and target.

How it works (`src/checks/group_aggregations.py`):

- Resolve a single partition key via `include_map` OR `table.column_map + include[1]`
- Build aligned subqueries projecting partition key `p`
- For each rule, aggregate per `p` on each side; compare with tolerances
- Report a sample of differing partitions and counts

Config fields

- `type: group_aggregations`
- Partition key (exactly one):
  - `include_map: { canon: {source, target} }` OR
  - `include: [canon]` + `table.column_map`
- `rules` like `aggregations` (methods and columns)
- `top_n`: cap diff sample size (default 50)
- Ordering options: `order_by`, `order_by_source`, `order_by_target`

Example

```yaml
- type: group_aggregations
  include_map:
    dim: { source: country_code, target: country_code }
  rules:
    - method: sum
      column: amount
    - method: count
```

Details output

```
details: {
  rules: [
    { method, column, source_column, target_column,
      tolerance_abs, tolerance_pct,
      diff_sample: [ {partition, source, target}, ... ],
      failed_partitions: <int>, pass: <bool> }
  ]
}
```

Status

- PASS if no diffs per rule; otherwise FAIL

