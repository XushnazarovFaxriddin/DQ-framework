# Custom SQL

Purpose: universal checker to execute arbitrary SQL and validate results.

Modes (`src/checks/custom_sql.py`):

- Single: run one SQL on the selected side (`'on': source|target`); infer PASS/FAIL by type or compare to `expected_result`.
- Dual: run `sql_source` on source and `sql_target` on target; compare results via `compare_mode`.

Config fields

- `type: custom_sql`
- Common:
  - `tolerance_abs`, `tolerance_pct` for numeric comparisons
  - `tolerance_time_sec`, `tolerance_time_min` for datetime tolerances
- Single mode:
  - `mode: single`
  - `'on': source|target` (default: source)  [YAML: quote the key `'on'`]
  - `sql: <SQL>`
  - `expected_result: <Any>` (optional)
- Dual mode:
  - `mode: dual`
  - `sql_source: <SQL>`
  - `sql_target: <SQL>`
  - `compare_mode: equals | greater | less`

Examples

```
# Single: implicit > 0 check for numerics
- type: custom_sql
  mode: single
  'on': source
  sql: "SELECT COUNT(*) FROM public.orders WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'"

# Single: expect exact value with datetime tolerance
- type: custom_sql
  mode: single
  'on': target
  sql: "SELECT MAX(updated_at) FROM `project.ds.orders`"
  expected_result: "2025-01-01T00:00:00Z"
  tolerance_time_min: 60

# Dual: compare row counts
- type: custom_sql
  mode: dual
  sql_source: "SELECT COUNT(*) FROM public.orders"
  sql_target: "SELECT COUNT(*) FROM `project.ds.orders`"
  compare_mode: equals
```

Type handling & comparison

- Numerics: equality with optional `tolerance_abs` and/or `tolerance_pct`.
- Datetimes: parsed/normalized to UTC. `tolerance_time_sec` or `tolerance_time_min` applies.
- Strings: trimmed equality; JSON (dict/list) compared by normalized JSON with sorted keys.
- Booleans: `True` → PASS, `False` → FAIL (when `expected_result` is not provided).
- `None`: treated as FAIL unless explicitly expected.

Details output

```
details (single): { mode, on, sql, result, expected_result? }
details (dual):   { mode, sql_source, sql_target, source_result, target_result, compare_mode }
```

Notes

- Always quote `'on'` in YAML for single‑mode. See Reference → YAML Quoting Rules.

