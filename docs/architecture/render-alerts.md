# Render & Alerts

## Rendering

- `summarize_run` builds a concise textual overview with counts and failure listings.
- `markdown_summary_table` produces a compact table for chat/email.
  - Aggregations expand per rule (e.g., `aggregations[sum]`).
  - Failed checks show difference percentage when available.

## Alerts Dispatcher (`src/alerts/dispatcher.py`)

- Iterates configured `alerts.routes`.
- Resolves recipients/webhook, invokes registered alert handlers.
- Skips when no routes are defined.

## Backends

### Google Chat (`gchat`)

- `mode: text|card` - text is simple lines, card is formatted Google Chat card
- `send_all_checks: true` to include passing checks
- Includes difference percentage for failed checks
- Shows Airflow context when env vars are set

### Email (`email`)

- Supports SMTP and SendGrid backends
- HTML and plain text formats
- Includes difference percentage, Airflow info, and CSV links
- See [Email Alerts](../aletrs/email.md) for details

## Alert Features

### Difference Percentage

For checks that compare counts (row_count, aggregations[count], aggregations[distinct_count]):
- Calculates percentage difference between source and target
- Displayed in alerts as "(diff: 2.3%)"
- Helps quickly assess severity of mismatches

### Critical Data Integrity Alerts

When `extra_in_target` is detected (target has records not in source):
- Alerts include a prominent warning section
- Email subject prefixed with "🚨 CRITICAL"
- Google Chat cards show red warning header
- Affected tables listed with record counts
- Links to CSV files for investigation

This is a critical data integrity issue that may indicate:
- Orphaned records in target
- Replication issues
- Unauthorized data insertion

### Airflow Integration

When Airflow environment variables are set:
- DAG ID, Task ID, Run ID displayed
- Direct links to task logs and DAG view
- Execution date for reference

Environment variables:
- `AIRFLOW_DAG_ID`, `AIRFLOW_TASK_ID`, `AIRFLOW_DAG_RUN_ID`
- `AIRFLOW_EXECUTION_DATE`
- `AIRFLOW_BASE_URL` (for constructing links)
- `AIRFLOW_LOG_URL`, `AIRFLOW_DAG_URL` (optional direct links)

### Mismatch CSV Links

When `mismatch_ids` is enabled:
- Links to CSV files containing mismatched IDs
- Separate files for `missing_in_target` and `extra_in_target` when configured
- CSV includes dashboard-ready metadata:
  - `id`, `mismatch_type`, `table_name`, `check_name`
  - `config_file`, `detection_timestamp`

## Google Chat Card Structure

```
┌─────────────────────────────────────┐
│ DQF Validation Summary - FAIL       │
│ Failures: 3 | Total: 10 | CRITICAL  │
├─────────────────────────────────────┤
│ 🚨 CRITICAL: Extra Records in Target│  ← Only if extra_in_target
│ (warning details...)                │
├─────────────────────────────────────┤
│ Failed Validations                  │
│ #1. orders                          │
│ Check: row_count                    │
│ Status: FAIL | Severity: WARNING    │
│ Metrics: source=1000 target=990     │
│          diff=10 diff_pct=1%        │
│ [Download mismatch CSV]             │
├─────────────────────────────────────┤
│ 📊 Airflow Run Info                 │  ← Only if Airflow vars set
│ DAG: daily_validation               │
│ Task: run_dqf                       │
│ [View Task Log] [View DAG]          │
└─────────────────────────────────────┘
```

## Email Structure

```
Subject: [DQF] CRITICAL - FAIL (3 failures)

┌─ HTML Email ───────────────────────┐
│ DQF Validation Report              │
│ Status: FAIL | Severity: CRITICAL  │
│                                    │
│ ⚠️ CRITICAL DATA INTEGRITY ALERT   │
│ Target has records not in source!  │
│ • orders/row_count: 50 extra       │
│                                    │
│ Failed Checks (with diff %)        │
│ ┌──────────┬────────┬──────┐      │
│ │ Table    │ Check  │ Diff │      │
│ ├──────────┼────────┼──────┤      │
│ │ orders   │row_cnt │ 1.2% │      │
│ └──────────┴────────┴──────┘      │
│                                    │
│ CSV Links: [Download]              │
│                                    │
│ 📊 Airflow: DAG | Task | Log      │
└────────────────────────────────────┘
```
