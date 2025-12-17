# Advanced Configuration

Use this page when you need deeper diagnostics, long‑term stats, dynamic tolerances, severity labels, and normalized exports.

## Mismatch sampling & CSV exports

Count-based checks (`row_count`, `aggregations` rules with `method: count` or `distinct_count`) can automatically scan ID ranges when totals diverge.

```yaml
results_storage:
  mismatch_csv:
    enabled: true
    backend: gcs
    bucket: dqf-results
    base_path: mismatch_ids
```

Enable sampling on the check:

```yaml
checks:
  - type: row_count
    id_column: RECORD_ID
    mismatch_sampling:
      mode: chunk           # or binary
      chunk_size: 200000
      max_scan_chunks: 50
      max_ranges: 5
  - type: aggregations
    rules:
      - method: distinct_count
        column: RECORD_ID
        id_column: RECORD_ID
        mismatch_sampling:
          mode: binary
          max_depth: 6
```

Outputs:
- `details.mismatch_ranges`: compact top ranges.
- `details.mismatch_csv_uri` (+ `mismatch_csv_uris`): CSV link stored in cloud storage. GChat/email alerts render a “Mismatch CSV” button (console URL) and a text link (public URL), avoiding giant JSON blobs.

Env defaults (see `.framework.env`):
- `DQF_RESULTS_BUCKET`, `DQF_RESULTS_BASE_PATH`, `DQF_RESULTS_PUBLIC_URL_PREFIX`
- `DQF_DEFAULT_MISMATCH_CHUNK_SIZE`, `DQF_DEFAULT_MISMATCH_MAX_RANGES`, `DQF_DEFAULT_MISMATCH_MAX_SCAN_CHUNKS`, `DQF_DEFAULT_MISMATCH_BINARY_DEPTH`

## Table stats & stats compare

`table_stats` writes per-period aggregates to a monitoring table (e.g., BigQuery), then `stats_compare` reads them back and compares source vs target by bucket.

```yaml
checks:
  - type: table_stats
    on: both
    time_column: SAIL_DATE_FROM
    time_granularity: month
    metrics:
      - method: count
        column: "*"
      - method: sum
        column: AMOUNT
      - method: avg
        column: PRICE
    stats_storage:
      backend: bigquery
      table: cert-shore-295415.dqf_monitoring.dqf_table_stats

  - type: stats_compare
    table_name: SEAWARE.RES_HEADER
    stats_table: cert-shore-295415.dqf_monitoring.dqf_table_stats
    compare_on:
      - period_granularity: month
        lookback_months: 12
      - period_granularity: day
        lookback_days: 30
    metrics:
      - method: count
        column: "*"
      - method: sum
        column: AMOUNT
    tolerance_pct: 0.75
```

Monitoring tables are defined in `scripts/bq_tables.sql` (`dqf_table_stats`, `dqf_check_results`, `dqf_runs`).

## Adaptive thresholds

Relax or tighten tolerances based on recency (first matching rule wins; fallback to the check’s base tolerance).

```yaml
adaptive_thresholds:
  - when: last_hours
    hours: 3
    tolerance_pct: 5.0
  - when: older_than_days
    days: 7
    tolerance_pct: 0.25
```

Applied in `stats_compare`, and in count-based checks when grouped by date.

## Severity rules

Map mismatches to `INFO|WARNING|CRITICAL` so alerts can prioritize issues.

```yaml
severity_rules:
  - condition: recent_small
    tolerance_pct_exceeded_lt: 0.5
    severity: INFO
  - condition: recent_large
    tolerance_pct_exceeded_gte: 0.5
    severity: WARNING
  - condition: old_period
    older_than_days: 30
    severity: CRITICAL
```

Severity propagates to `CheckResult.severity` and `RunResult.overall_severity` and is shown in email/GChat subjects and card headers.

## Results persistence (runs & checks)

Store normalized run/check rows in a warehouse for dashboards and audits.

```yaml
results_storage:
  runs:
    enabled: true
    backend: bigquery
    table: cert-shore-295415.dqf_monitoring.dqf_runs
  checks:
    enabled: true
    backend: bigquery
    table: cert-shore-295415.dqf_monitoring.dqf_check_results
```

Rows include status, severity, counts, and references such as `mismatch_csv_uri` and `stats_table`; only small summaries are stored (no huge JSON).

## Alerting highlights

- Text mode: shows status + compact CSV previews.
- Card mode: shows context (env, config file, run label, time window), failed checks, and:
  - “Download mismatch CSV” text link (public URL).
  - “Mismatch CSV” button (Cloud Console object view).
  - Severity badge from rules above.

## Summary

All advanced blocks are optional and default to safe no-op behavior. Start with basics, then layer in sampling, stats, adaptive thresholds, severity, and persistence as needed. Python configs can express the same schema programmatically.
