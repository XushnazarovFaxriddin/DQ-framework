# Email Alerts (SMTP & SendGrid)

Module: `src/alerts/email.py`

## Backends

DQF supports two email backends:

### SMTP Backend (default)

Standard SMTP with optional STARTTLS or SSL encryption.

Environment variables:
- `SMTP_HOST` (required): SMTP server hostname
- `SMTP_PORT` (default: `587`): SMTP server port
- `SMTP_FROM` (default: `dqf@localhost`): sender email address
- `SMTP_USER`: username for authentication
- `SMTP_PASS`: password for authentication
- `SMTP_STARTTLS` (default: `true`): enable STARTTLS encryption
- `SMTP_SSL` (default: `false`): use SSL connection (mutually exclusive with STARTTLS)

### SendGrid Backend

Uses SendGrid API for reliable email delivery.

Environment variables:
- `SENDGRID_API_KEY` (required): your SendGrid API key
- `SENDGRID_FROM`: sender email (falls back to `SMTP_FROM`)

To use SendGrid, set:
```bash
export DQF_EMAIL_BACKEND=sendgrid
export SENDGRID_API_KEY=SG.xxx...
export SENDGRID_FROM=dqf@yourcompany.com
```

## Features

### Difference Percentage

For failed checks, emails display the percentage difference between source and target:
- Works with `row_count`, `aggregations[count]`, `aggregations[distinct_count]`
- Shown in both the summary table and individual check listings

### Critical Data Integrity Alerts

When target contains records that don't exist in source (`extra_in_target`):
- Subject line prefixed with "🚨 CRITICAL"
- Prominent warning section in email body
- Lists affected tables with record counts
- Links to CSV files for investigation

### Airflow Integration

When Airflow environment variables are set, emails include:
- DAG ID, Task ID, Run ID
- Direct links to task logs and DAG view
- Execution date for reference

Set these in your DAG:
```python
env_vars={
    "AIRFLOW_DAG_ID": "{{ dag.dag_id }}",
    "AIRFLOW_TASK_ID": "{{ task.task_id }}",
    "AIRFLOW_DAG_RUN_ID": "{{ dag_run.run_id }}",
    "AIRFLOW_EXECUTION_DATE": "{{ ds }}",
    "AIRFLOW_BASE_URL": "https://airflow.yourcompany.com",
}
```

### Mismatch CSV Links

When `mismatch_ids` is enabled, emails include:
- Links to CSV files containing mismatched IDs
- Separate files for `missing_in_target` and `extra_in_target`
- Dashboard-ready metadata in each CSV

## Route Configuration (YAML)

```yaml
alerts:
  routes:
    - kind: email
      to: ["user@example.com", "dq-team@corp.com"]
```

## Recipient Resolution

1. Route `to:` field (if specified)
2. `DQ_EMAILS` environment variable (comma-separated)

## Email Format

Emails are sent in both plain text and HTML formats:

### HTML Format
- Styled tables for failed checks
- Color-coded severity indicators
- Clickable links for CSVs and Airflow
- Prominent critical warning sections

### Plain Text Format
- Clean, readable summary
- All links included as URLs
- Compatible with text-only email clients

## Attachments

CSV previews are automatically attached for:
- `missing_on_target` samples
- `extra_on_target` samples
- `mismatch_sample` data
- `diff_sample` data

Limited to 3 attachments to avoid email size limits.

## Example Email Content

```
DQF Validation Report
Status: FAIL
Severity: CRITICAL

⚠️ CRITICAL DATA INTEGRITY ALERT
Target database contains records that DO NOT EXIST in source!
  - orders/row_count: 1,234 extra records

Failed Checks:
  - orders/row_count (diff: 2.3%)
  - customers/aggregations[count] (diff: 0.5%)

Mismatch CSV Files:
  - orders/row_count: gs://bucket/path/orders-20251218_120000.csv

📊 Airflow Run Info:
  DAG: daily_validation
  Task: run_dqf
  📋 Task Log: https://airflow.example.com/...
```
