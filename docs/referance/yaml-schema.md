# YAML Schema Reference

The config is validated against `ConfigModel` (`src/compiler/schema.py`).

Top‑level keys

- `connections` (required)
- `tables` (required)
- `defaults` (optional)
- `planning` (optional)
- `alerts` (optional)
- `results_storage` (optional)

connections

```yaml
connections:
  source_env_var: <ENV_VAR_NAME>
  target_env_var: <ENV_VAR_NAME>
  source_type: <optional engine>
  target_type: <optional engine>
```

defaults

```yaml
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

```yaml
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

```yaml
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

Mismatch sampling (row_count / aggregations)

```yaml
mismatch_sampling:
  mode: chunk | binary
  chunk_size: <int>           # defaults to DQF_DEFAULT_MISMATCH_CHUNK_SIZE
  max_ranges: <int>           # defaults to DQF_DEFAULT_MISMATCH_MAX_RANGES
  max_scan_chunks: <int>      # defaults to DQF_DEFAULT_MISMATCH_MAX_SCAN_CHUNKS
  max_depth: <int>            # defaults to DQF_DEFAULT_MISMATCH_BINARY_DEPTH
  range_start: <int>          # optional lower bound for sampled IDs
  range_end: <int>            # optional upper bound for sampled IDs
```

`row_count` and `aggregations` (count rules) can include this block to drive chunked or binary search scans when global counts do not match. Use `results_storage.mismatch_csv.enabled: true` plus the `DQF_RESULTS_*` env vars to persist the sampled ranges to CSV and share the URI.

Adaptive thresholds

```yaml
adaptive_thresholds:
  - when: last_hours
    hours: 4
    tolerance_pct: 10.0
  - when: older_than_days
    days: 7
    tolerance_pct: 0.5
    tolerance_abs: 100
```

The list is evaluated in order; the first matching rule supplies its tolerances and the search stops. If no rule matches, the check falls back to `tolerance_pct`/`tolerance_abs`. This lets you relax tolerances for very recent buckets (e.g. `last_hours`) while keeping older data strict.

Severity rules

```yaml
severity_rules:
  - condition: "recent_small"
    tolerance_pct_exceeded_lt: 0.5
    severity: INFO
  - condition: "recent_large"
    tolerance_pct_exceeded_gte: 0.5
    severity: WARNING
  - condition: "old"
    older_than_days: 30
    severity: CRITICAL
```

The first matching rule publishes its `severity` (`INFO`/`WARNING`/`CRITICAL`) to the `CheckResult.severity`, which also drives the run-level `overall_severity` and alert titles. Leave `severity_rules` unset to keep the default warning-level semantics.

Table stats

```yaml
- type: table_stats
  on: source | target | both
  time_column: <timestamp column>
  time_granularity: day | week | month | year
  metrics:
    - method: count
      column: "*"
    - method: sum
      column: revenue
    - method: avg
      column: price
  stats_storage:
    backend: bigquery
    table: cert-shore-295415.dqf_monitoring.dqf_table_stats
    project: <optional project>
```

`table_stats` aggregates metrics per time bucket and writes them into the monitoring table defined by `stats_storage` (or the `DQF_STATS_TABLE` env var when the section is omitted). Valid metric methods: `count`, `sum`, `avg`, `min`, `max`, `distinct_count`.

Stats compare

```yaml
- type: stats_compare
  stats_table: cert-shore-295415.dqf_monitoring.dqf_table_stats
  stats_table_side: target  # source|target
  table_name: <logical table name>
  compare_on:
    - period_granularity: month
      lookback_months: 12
    - period_granularity: day
      lookback_days: 30
  metrics:
    - method: count
      column: "*"
    - method: sum
      column: revenue
  tolerance_pct: 1.0
  tolerance_abs: 0.0
```

`stats_compare` reads rows written by `table_stats` from `stats_table` (or `DQF_STATS_TABLE`) via the selected connector and compares `metric_value` across `source`/`target`. Use `compare_on` entries to scope the time buckets and `metrics` to mirror the aggregated metrics you collected.

The check produces compact metadata in the result:

- `details.summary` includes `periods_checked`, `mismatched_periods`, `severity` (HIGH/MEDIUM/LOW based on age), and `oldest_mismatch`.
- `details.reference` restates `stats_table`, `table_name`, the lookback cutoff, and the configured granularities so downstream consumers can query the raw history if needed.
- `details.mismatches` is limited to 10 rows sorted by `diff` and annotated with `severity`/`age_days`; you can still wire this to alerts without embedding massive JSON.

Freshness (example of specialized fields)

```yaml
column | col: <timestamp column>
'on': source | target   # YAML: quote the key 'on'
max_lag_minutes: <int>
```

Custom SQL (partial)

```yaml
mode: single | dual
sql: <SQL for single mode>
sql_source: <SQL>
sql_target: <SQL>
expected_result: <Any>
compare_mode: equals | less | greater
```

Join Rowdiff

```yaml
join_keys:
  source: [ expr, ... ]
  target: [ expr, ... ]   # same length
```

planning (PlanningCfg)

```yaml
planning:
  partitions:
    mode: none | rolling_days | rolling_hours | range
    window: <int>
    start: <iso8601>
    end:   <iso8601>
```

alerts (AlertsCfg)

```yaml
alerts:
  routes:
    - kind: gchat
      mode: text | card
    - kind: email
      to: [ "user@example.com" ]
```

results_storage

```yaml
results_storage:
  mismatch_csv:
    enabled: true
    backend: gcs | local
    bucket: <bucket name>
    base_path: <path prefix>
    public_url_prefix: <optional url prefix>
  runs:
    enabled: true
    backend: bigquery
    table: dqf_monitoring.dqf_runs
    project: cert-shore-295415
  checks:
    enabled: true
    backend: bigquery
    table: dqf_monitoring.dqf_check_results
    project: cert-shore-295415
```

- `mismatch_csv`: optional export of mismatch diagnostics used by row_count/aggregations sampling. You can leave `bucket`/`base_path` empty to inherit the `DQF_RESULTS_*` env variables in `.framework.env`.
- `runs` / `checks`: toggle inserting normalized run/check rows into a backend table (BigQuery by default). They are independent flags, so you can persist only run summaries, only check rows, or both.
- Each section supports `enabled`, `backend`, `table`, and optional `project`. The default backend is `bigquery` (requires `google-cloud-bigquery`). Persisted rows include run id, status, counts, severity, and small references (`mismatch_csv_uri`, `stats_table`, `summary`, etc.) so dashboards can consume the data without large JSON payloads.

YAML quoting note

- YAML 1.1 treats bare words like `on`, `off`, `yes`, `no` as booleans. Always quote the key `'on'` in check configs when selecting side. Example:

```yaml
- type: domain
  'on': source
  column: email
```

