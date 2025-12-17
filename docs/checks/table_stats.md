# Table Statistics

Purpose: compute per-period aggregates (counts, sums, averages, etc.) and persist the results to a monitoring table so downstream dashboards or comparisons can pick up the history.

How it works (`src/checks/table_stats.py`):

- Determine which side(s) to sample (`on: source | target | both`), then take the rendered base `SELECT` from each connector.
- Build SQL that buckets rows by the configured `time_column` and `time_granularity` (day/week/month/year) using the native truncation/interval functions per engine.
- Compute each metric in `metrics` along with a bucket row count.
- Normalize the result into the monitoring schema and insert rows into the configured stats storage backend (`bigquery` by default).

Configuration

- `type: table_stats`
- `on`: `source`, `target`, or `both` (default: `source`).
- `time_column`: column used for bucketing; `time_column_source` and `time_column_target` override per side.
- `time_granularity`: `day`, `week`, `month`, or `year`.
- `metrics`: list of metric descriptors with:
  - `method`: `count`, `sum`, `avg`, `min`, `max`, or `distinct_count`.
  - `column`: column name (`count` accepts `*`).
  - `name`: optional friendly metric label (defaults to `method:column`).
- `stats_storage`: where to persist results. Example:

```yaml
stats_storage:
  backend: bigquery
  table: cert-shore-295415.dqf_monitoring.dqf_table_stats
```

`TableStatsStorageCfg.table` can be supplied via the `DQF_STATS_TABLE` env var (`.framework.env` already points to `cert-shore-295415.dqf_monitoring.dqf_table_stats`). Optionally override `project` with `DQF_STATS_PROJECT`.

Example

```yaml
connections:
  source_env_var: MONITORING_BQ
  target_env_var: MONITORING_BQ
  source_type: bigquery
  target_type: bigquery

tables:
  - name: dqf_runs_stats
    source:
      table: cert-shore-295415.dqf_monitoring.dqf_runs
    target:
      table: cert-shore-295415.dqf_monitoring.dqf_runs
    checks:
      - type: table_stats
        on: source
        time_column: started_at
        time_granularity: day
        metrics:
          - method: count
            column: "*"
          - method: sum
            column: pass_count
          - method: sum
            column: fail_count
        stats_storage:
          backend: bigquery
          table: cert-shore-295415.dqf_monitoring.dqf_table_stats
```

Monitoring table

Create the destination table before running this check (see `scripts/bq_tables.sql`, section `dqf_table_stats`). Replace `cert-shore-295415` with your project/dataset if needed.

Result details

- `status`: `RECORDED` when rows were inserted, `SKIP` when no storage is configured or no metrics produced rows, `FAIL` if persistence failed.
- `details`: `{ stats_table: <table>, rows: <int>, run_timestamp: <iso> }`

Stats comparison

Use `stats_compare` (see `docs/checks/stats_compare.md`) to read back the rows you just wrote and compare `source` vs `target` per period bucket. The same `stats_storage.table`, `table_name`, and `metrics` apply so the comparison works out of the box.

See `config/yaml/table_stats_example.yaml` for another usage pattern that pairs this check with the monitoring dataset and `results_storage.mismatch_csv`.
