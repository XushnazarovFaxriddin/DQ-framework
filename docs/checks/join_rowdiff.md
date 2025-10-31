# Join Rowdiff

Purpose: key‑based row comparison with per‑column diffs and tolerances.

How it works (`src/checks/join_rowdiff.py`):

- Resolves aligned compare columns using one of four patterns (priority):
  1) `include_map` — canonical → {source, target}
  2) `table.column_map` + `include` (canonical)
  3) Pairwise `include_source` + `include_target` (same length; optional `include` to name canonicals)
  4) `include` only (identical names)
- Adds join keys as `k1..kn` into aligned projections
- Fetches bounded DataFrames (ORDER BY/LIMIT) from both sides
- Outer merges on keys and classifies rows:
  - missing on target (left‑only)
  - extra on target (right‑only)
  - mismatched cells (present on both; per‑cell comparison with tolerance)
- Tolerances: global `tolerance_abs`/`tolerance_pct`, and per‑column overrides via `rules: [{ col|column, tolerance_abs, tolerance_pct }]`
- Deterministic ordering via `order_by` (canonical → mapped) or per‑side overrides

Required

- `join_keys.source: [ expr, ... ]`
- `join_keys.target: [ expr, ... ]` with the same length

Examples (column alignment)

```
# Via table.column_map + include
- type: join_rowdiff
  join_keys:
    source: ["order_id"]
    target: ["order_id"]
  include: [amount, status, updated_at]

# Explicit include_map
- type: join_rowdiff
  join_keys:
    source: ["id"]
    target: ["id"]
  include_map:
    amount:     { source: "ROUND(amount,2)", target: "CAST(total_amount AS NUMERIC)" }
    status:     { source: "status",          target: "status" }
    updated_at: { source: "updated_at",      target: "updated_at" }

# Pairwise include_source/target with optional canonical names
- type: join_rowdiff
  join_keys:
    source: ["order_id"]
    target: ["OrderId"]
  include: [amount, status, updated_at]
  include_source: [amount, status, updated_at]
  include_target: [total_amount, status, updated_at]
```

Tolerances

```
- type: join_rowdiff
  join_keys: { source: ["id"], target: ["id"] }
  include: [amount, updated_at]
  tolerance_abs: 0.5     # apply to all compare columns
  tolerance_pct: 1.0
  rules:
    - { col: "amount", tolerance_abs: 0.01 }     # per-column override
```

Ordering & sampling

```
- type: join_rowdiff
  join_keys: { source: ["id"], target: ["id"] }
  include: [amount, status]
  order_by: [id]                                  # canonical → mapped per side
  # or per side:
  # order_by_source: ["created_at", "id"]
  # order_by_target: ["created_at", "id"]
```

Details output (compact)

```
details: {
  mismatch_total_estimate: <int>,
  canonical: [ ... ],
  missing_count_on_target: <int>,
  extra_count_on_target: <int>
}
```

Performance notes

- Use planner partitions to reduce working set size for large tables.
- Keep `max_rows_preview` reasonable (CLI/vars; default 1000) to bound memory.
- Push column projection and filters into `QueryCfg.select`/`query` to shrink frames.

