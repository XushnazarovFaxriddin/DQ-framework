# Results Persistence

DQF can persist validation run results and check outcomes to BigQuery for historical analysis, dashboarding, and monitoring.

## Overview

Results persistence enables:
- **Run tracking**: Store summary of each DQF run with timing and status
- **Check history**: Store individual check results with metrics and details
- **Trend analysis**: Query historical data to detect patterns
- **Alerting integration**: Use BigQuery for downstream alert systems

## Configuration

### Environment Variables

```bash
# Optional: BigQuery tables for results persistence
DQF_RUNS_TABLE=project.dataset.dqf_runs
DQF_CHECKS_TABLE=project.dataset.dqf_check_results
```

### YAML Configuration

```yaml
results_storage:
  runs:
    enabled: true
    backend: bigquery
    table: project.dataset.dqf_runs
    project: optional-override-project
  checks:
    enabled: true
    backend: bigquery
    table: project.dataset.dqf_check_results
    project: optional-override-project
```

## BigQuery Table Schemas

### dqf_runs Table

Stores summary information for each DQF validation run.

```sql
CREATE TABLE IF NOT EXISTS dqf_runs (
  run_id STRING NOT NULL,
  config_file STRING,
  env STRING,
  run_label STRING,
  status STRING NOT NULL,  -- PASS, FAIL, ERROR
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  duration_ms INT64,
  total_checks INT64,
  passed_checks INT64,
  failed_checks INT64,
  skipped_checks INT64,
  tables_processed INT64,
  has_critical_issues BOOL,  -- True if any extra_in_target detected
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY config_file, env;
```

### dqf_check_results Table

Stores individual check results with detailed metrics.

```sql
CREATE TABLE IF NOT EXISTS dqf_check_results (
  run_id STRING NOT NULL,
  config_file STRING,
  env STRING,
  table_name STRING NOT NULL,
  check_type STRING NOT NULL,
  status STRING NOT NULL,  -- PASS, FAIL, SKIP, RECORDED
  severity STRING,  -- INFO, WARNING, CRITICAL
  source_value FLOAT64,
  target_value FLOAT64,
  has_extra_in_target BOOL,
  extra_in_target_count INT64,
  mismatch_ids_csv_uri STRING,
  details_json STRING,  -- Full details as JSON
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY config_file, table_name, check_type;
```

### dqf_table_stats Table

Stores time-series statistics collected by `table_stats` check.

```sql
CREATE TABLE IF NOT EXISTS dqf_table_stats (
  run_id STRING,
  config_file STRING,
  env STRING,
  table_name STRING NOT NULL,
  side STRING,  -- source, target
  time_column STRING,
  period_granularity STRING,  -- day, week, month, year
  period_start TIMESTAMP,
  period_end TIMESTAMP,
  period_key STRING,
  metric_name STRING NOT NULL,
  column_name STRING,
  metric_value FLOAT64,
  row_count INT64,
  computed_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(period_start)
CLUSTER BY table_name, metric_name, period_granularity;
```

## Usage

### Automatic Persistence

When tables are configured, results are automatically persisted after each run:

1. Run summary is inserted into `dqf_runs`
2. Each check result is inserted into `dqf_check_results`
3. `table_stats` metrics are inserted into `dqf_table_stats`

### Querying Results

```sql
-- Recent failed runs
SELECT run_id, config_file, status, duration_ms, failed_checks
FROM dqf_runs
WHERE status = 'FAIL'
  AND created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY created_at DESC;

-- Critical issues (extra_in_target)
SELECT r.run_id, c.table_name, c.check_type, c.extra_in_target_count
FROM dqf_check_results c
JOIN dqf_runs r ON c.run_id = r.run_id
WHERE c.has_extra_in_target = true
  AND c.created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR);

-- Check pass rate by table
SELECT
  table_name,
  check_type,
  COUNTIF(status = 'PASS') AS passed,
  COUNTIF(status = 'FAIL') AS failed,
  ROUND(COUNTIF(status = 'PASS') / COUNT(*) * 100, 2) AS pass_rate
FROM dqf_check_results
WHERE created_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY table_name, check_type
ORDER BY pass_rate ASC;

-- Stats trend analysis
SELECT
  period_key,
  metric_name,
  AVG(metric_value) AS avg_value,
  MAX(metric_value) AS max_value
FROM dqf_table_stats
WHERE table_name = 'orders'
  AND period_granularity = 'day'
  AND period_start > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY period_key, metric_name
ORDER BY period_key;
```

## Integration with Alerts

Results persistence integrates with alerting:

1. **Critical Detection**: `has_critical_issues` flag in runs indicates extra_in_target issues
2. **CSV Links**: `mismatch_ids_csv_uri` in check results links to exported CSVs
3. **Severity Tracking**: `severity` field enables filtering by issue importance

## Best Practices

1. **Partition by date**: Improves query performance and cost
2. **Cluster wisely**: `config_file`, `table_name`, `check_type` are common filters
3. **Monitor costs**: Set up BigQuery cost alerts for high-volume validation
4. **Retention policy**: Consider table expiration for old data
5. **Access control**: Use IAM to restrict who can query results
