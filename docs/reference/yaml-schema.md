# YAML Schema Reference

The config is validated against `ConfigModel` (`src/compiler/schema.py`).

Top‑level keys

- `connections` (required)
- `tables` (required)
- `defaults` (optional)
- `planning` (optional)
- `alerts` (optional)

connections

```
connections:
  source_env_var: <ENV_VAR_NAME>
  target_env_var: <ENV_VAR_NAME>
  source_type: <optional engine>
  target_type: <optional engine>
```

defaults

```
defaults:
  row_limit: 1000
  thresholds: {}
  hashing:
    algorithm: double_md5 | md5_row | sha256_row
    null_token: ""
    delimiter: "|"
    case: none | lower | upper
```

tables[] (TableCfg)

```
tables:
  - name: <string>
    dynamic_pattern: false
    source: QueryCfg
    target: QueryCfg
    column_map:
      canonical_name: { source: <expr>, target: <expr> }
    checks: [ CheckCfg, ... ]
```

QueryCfg

- `table` only → `SELECT * FROM table`
- `table` + `select` → `SELECT <select> FROM table`
- `query` only → used as provided
- Hints: `order_by: [ ... ]`, `filters: { ... }` (freeform)

CheckCfg (union of fields used across built‑ins)

Selection/mapping

```
type: <check name>
include: [ canonical ]
include_source: [ source exprs ]
include_target: [ target exprs ]
include_map:
  canonical:
    source: <expr>
    target: <expr>
exclude: [ canonical ]
order_by: [ canonical ]
order_by_source: [ source exprs ]
order_by_target: [ target exprs ]
```

Freshness (example of specialized fields)

```
column | col: <timestamp column>
'on': source | target   # YAML: quote the key 'on'
max_lag_minutes: <int>
```

Custom SQL (partial)

```
mode: single | dual
sql: <SQL for single mode>
sql_source: <SQL>
sql_target: <SQL>
expected_result: <Any>
compare_mode: equals | less | greater
```

Join Rowdiff

```
join_keys:
  source: [ expr, ... ]
  target: [ expr, ... ]   # same length
```

planning (PlanningCfg)

```
planning:
  partitions:
    mode: none | rolling_days | rolling_hours | range
    window: <int>
    start: <iso8601>
    end:   <iso8601>
```

alerts (AlertsCfg)

```
alerts:
  routes:
    - kind: gchat
      mode: text | card
      webhook: <optional if GCHAT_DQ_WEBHOOK set>
    - kind: email
      to: [ "user@example.com" ]
```

YAML quoting note

- YAML 1.1 treats bare words like `on`, `off`, `yes`, `no` as booleans. Always quote the key `'on'` in check configs when selecting side. Example:

```
- type: domain
  'on': source
  column: email
```

