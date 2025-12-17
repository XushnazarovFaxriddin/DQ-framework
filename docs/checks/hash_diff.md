# Hash Diff

Purpose: value parity across aligned columns using deterministic per‑row hashes.

How it works (`src/checks/hash_diff.py`):

- Build aligned projections for source and target using one of four patterns (priority):
  1) `include_map` — canonical → {source, target}
  2) `table.column_map` + `include` (canonical)
  3) Pairwise `include_source` + `include_target` (same length; optional `include` for canonical names)
  4) `include` only (identical column names on both sides)
- Render base `SELECT` for each side (`connector.render_select_sql`), then project aligned columns.
- Optionally apply `ORDER BY`/`LIMIT` for deterministic, bounded previews (engine‑aware via `wrap_order_by_limit`).
- Compute a row hash over canonical columns using each connector’s `hash_expr` honoring `defaults.hashing`.
- Compare hash sets; missing/extra indicate mismatches.

Config fields

- `type: hash_diff`
- Column selection (choose one pattern):
  - `include_map: { canon: { source: <expr>, target: <expr> }, ... }`
  - `include: [canon, ...]` with `table.column_map`
  - `include_source: [expr, ...]` + `include_target: [expr, ...]` (same length)
  - `include: [identical_names]` (no mapping)
- Ordering (optional):
  - `order_by: [canonical]` → mapped to each side when per‑side overrides are absent
  - `order_by_source: [raw exprs]`, `order_by_target: [raw exprs]`

Hashing policy (from `defaults.hashing`)

- `algorithm`: `double_md5` (default) | `md5_row` | `sha256_row`
- `null_token`, `delimiter`, `case` (`none|lower|upper`) per token
- Connector implementations ensure parity across engines (see connectors docs).

Examples

```yaml
# via table.column_map + include
- type: hash_diff
  include: [id, api_id, amount]

# explicit mapping
- type: hash_diff
  include_map:
    id:      { source: id,        target: id }
    api_id:  { source: api_id,    target: ApiId }
    amount:  { source: "ROUND(amount,2)", target: "CAST(total_amount AS NUMERIC)" }

# pairwise
- type: hash_diff
  include_source: [id, api_id, amount]
  include_target: [id, ApiId, total_amount]
  order_by: [id]
```

Details output (compact)

```
details: {
  algorithm: <algorithm>,
  canonical: [ ... ],
  missing_count: <int>,
  extra_count: <int>
}
```

Notes

- Prefer `include_map` or `table.column_map + include` for unambiguous alignment.
- Ensure hashing policy is consistent across connectors you compare.

