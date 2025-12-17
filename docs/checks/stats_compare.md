# Stats Compare

Purpose: validate the statistics already persisted by the `table_stats` check and flag periods where `source`/`target` aggregates diverge.

How it works (`src/checks/stats_compare.py`):

- Reads from a stats table (default: `DQF_STATS_TABLE`, typically `dqf_monitoring.dqf_table_stats`) via the configured connector (`stats_table_side`, default `target`).
- Filters the stats rows by `table_name`, `period_granularity`, and `period_start` lookback window (`compare_on`).
- Compares `metric_value` for each `metric_name` across `source` and `target`, honoring `tolerance_pct`/`tolerance_abs`.
- Records mismatches (missing side, out-of-tolerance) in `details.mismatches` for downstream alerts.

Configuration

- `stats_table`: BigQuery/geographic table that stores stats (defaults to `DQF_STATS_TABLE` env var).
- `stats_table_side`: `source` or `target` connector to use when querying the stats table (default: `target`).
- `table_name`: logical name that was recorded by `table_stats` (defaults to the current `table` block).
- `compare_on`: list of buckets to inspect; each entry sets `period_granularity` plus lookbacks (`lookback_days`, `lookback_weeks`, etc.).
- `metrics`: reuse the same metric descriptors as `table_stats`. The computed metric names (`name` or `method:column`) drive which rows are compared.
- `tolerance_pct` / `tolerance_abs`: apply the same tolerances as other checks.
- `severity_rules`: optional list of INFO/WARNING/CRITICAL lookups that inspect each mismatch (age, percentage diff, etc.) and determine how urgent the violation is. Rules are evaluated in order and the first match wins; unspecified runs default to `WARNING`.
- `adaptive_thresholds`: optional rules that can shrink or grow tolerances by age (e.g., `last_hours` versus `older_than_days`). The first matching rule wins and overrides `tolerance_pct`/`tolerance_abs` for that bucket.

Example

```yaml
- type: stats_compare
  stats_table: cert-shore-295415.dqf_monitoring.dqf_table_stats
  table_name: DQF_RUNS_STATS
  stats_table_side: target
  compare_on:
    - period_granularity: month
      lookback_months: 12
    - period_granularity: day
      lookback_days: 30
  metrics:
    - method: count
      column: "*"
    - method: sum
      column: pass_count
    - method: sum
      column: fail_count
  tolerance_pct: 1.0
  severity_rules:
    - condition: "recent_small"
      tolerance_pct_exceeded_lt: 0.5
      severity: "INFO"
    - condition: "recent_large"
      tolerance_pct_exceeded_gte: 0.5
      severity: "WARNING"
    - condition: "old_period"
      older_than_days: 30
      severity: "CRITICAL"
```

Result details

- `status`: `PASS` when all requested windows are in tolerance, `FAIL` otherwise.
- `details`: includes `{ stats_table, table_name, metrics, windows, rows_examined, mismatch_count, summary, reference, mismatches }`.
- `details.summary`: top-level stats for the check (`periods_checked`, `mismatched_periods`, `severity`, `severity_level`, and the oldest mismatch timestamp so you know how far back the failure reaches).
- `details.reference`: quick filters (`stats_table`, `table_name`, `lookback_cutoff`, `granularities`) so alerting systems or analysts can inspect the stored history directly.
- `details.mismatches`: up to 10 worst violations (oldest first) with `metric_name`, `period_key`, `source_value`, `target_value`, `diff`, `pct_diff`, `reason`, `severity`, `severity_level`, and `age_days`. The `severity_level` matches the `CheckResult.severity` so alerts can prioritize the most urgent buckets.

Severity tiering

- `severity` is derived from period age: mismatch ages >= 180 days map to `HIGH`, >= 60 days map to `MEDIUM`, otherwise `LOW`. The check continues to surface this label in `details.summary.severity` and each mismatch row so alerts can highlight how stale the discrepancies are.
- `severity_level` (INFO/WARNING/CRITICAL) is driven by `severity_rules` and shows up on the `CheckResult`/`RunResult` severity fields plus `details.summary.severity_level`. Alerts use this signal to bubble up critical mismatches without embedding large payloads.
- Because the summary limits the recorded violations to the top N by delta, no huge JSON blobs are dumped even when the lookback windows are wide.
