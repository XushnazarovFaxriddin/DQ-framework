# Row Count

Purpose: compare row counts between source and target selections.

How it works (`src/checks/row_count.py`):

- Renders base `SELECT` for source/target via connectors
- Optionally wraps with `ORDER BY` for deterministic semantics on certain engines
- Wraps into `SELECT COUNT(*) FROM (<base>)`
- Compares integers for equality

Config fields

- `type: row_count`
- Ordering options (optional):
  - `order_by: [ canonical cols ]` → mapped via `table.column_map` to each side
  - `order_by_source: [ raw exprs ]` overrides for source
  - `order_by_target: [ raw exprs ]` overrides for target

Examples

```
- type: row_count

- type: row_count
  order_by: [id]

- type: row_count
  order_by_source: ["created_at", "id"]
  order_by_target: ["created_at", "id"]
```

Details output

```
details: { source_count: <int>, target_count: <int> }
```

Status

- PASS if counts equal; otherwise FAIL

