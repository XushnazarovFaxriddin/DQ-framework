# Environment Variables

Framework

- `DQF_CONCURRENCY`: default for `--concurrency`.
- `DQF_CONCURRENCY_CHECKS`: default for `--concurrency_checks`.
- `DQF_TABLE_TIMEOUT`: default for `--table_timeout_sec`.
- `DQF_CHECK_TIMEOUT`: default for `--check_timeout_sec`.
- `DQF_MAX_ROWS_PREVIEW`: default for `--max_rows_preview`.
- `DQF_DISABLE_CHECKS`: comma-separated check names to disable.
- `DQF_EXTRA_CHECKS`: comma-separated module paths to import.
- `DQF_DEFAULT_MISMATCH_CHUNK_SIZE`: default `chunk_size` for `mismatch_sampling` chunk mode.
- `DQF_DEFAULT_MISMATCH_MAX_RANGES`: default `max_ranges` for sampling summaries.
- `DQF_DEFAULT_MISMATCH_MAX_SCAN_CHUNKS`: default `max_scan_chunks` for sampling scans.
- `DQF_DEFAULT_MISMATCH_BINARY_DEPTH`: default `max_depth` for binary search sampling.
- `DQF_RESULTS_BACKEND`: default backend for `results_storage.mismatch_csv` (`local` or `gcs`).
- `DQF_RESULTS_BUCKET`: bucket name used with the GCS backend.
- `DQF_RESULTS_BASE_PATH`: folder prefix inside the bucket or artifacts directory.
- `DQF_RESULTS_PUBLIC_URL_PREFIX`: optional HTTP prefix to turn `gs://` paths into public URLs.
- `DQF_RUNS_TABLE`: optional default for `results_storage.runs.table`.
- `DQF_CHECKS_TABLE`: optional default for `results_storage.checks.table`.
- `DQF_STATS_TABLE`: fallback BigQuery table for the `table_stats` check (`cert-shore-295415.dqf_monitoring.dqf_table_stats` by default).
- `DQF_STATS_PROJECT`: optional project override when the stats table is unqualified.

Mismatch IDs Detection

- `DQF_MISMATCH_IDS_ENABLED`: enable mismatch IDs detection (`true` or `false`, default: `true`).
- `DQF_MISMATCH_IDS_CHUNK_SIZE`: chunk size for ID comparison (default: `500000`). Optimized for 10M+ rows.
- `DQF_MISMATCH_IDS_MAX_IDS`: maximum IDs to include in CSV export (default: `100000`).
- `DQF_MISMATCH_IDS_PARALLEL_CHUNKS`: number of parallel chunks for processing (default: `4`).

Alerts

- `GCHAT_DQ_WEBHOOK`: webhook for Google Chat backend (if not provided in route).
- `DQ_EMAILS`: default recipient list for email backend when `to:` omitted.
- `DQF_EMAIL_BACKEND`: email backend to use (`smtp` or `sendgrid`, default: `smtp`).
- `DQF_EMAIL_SUBJECT`: subject prefix for email.

SMTP Configuration

- `SMTP_HOST`: SMTP server hostname (required for SMTP backend).
- `SMTP_PORT`: SMTP server port (default: `587`).
- `SMTP_FROM`: sender email address (default: `dqf@localhost`).
- `SMTP_USER`: SMTP username for authentication.
- `SMTP_PASS`: SMTP password for authentication.
- `SMTP_STARTTLS`: enable STARTTLS (default: `true`).
- `SMTP_SSL`: use SSL connection instead of STARTTLS (default: `false`).

SendGrid Configuration

- `SENDGRID_API_KEY`: SendGrid API key (required for SendGrid backend).
- `SENDGRID_FROM`: sender email address for SendGrid (falls back to `SMTP_FROM`).

Airflow Integration

Set these environment variables in your Airflow DAG to enable automatic linking in alerts:

- `AIRFLOW_DAG_ID`: DAG identifier.
- `AIRFLOW_DAG_RUN_ID`: current DAG run identifier.
- `AIRFLOW_TASK_ID`: task identifier.
- `AIRFLOW_EXECUTION_DATE`: execution date/time.
- `AIRFLOW_LOG_URL`: direct link to task log (optional, constructed automatically if base URL provided).
- `AIRFLOW_DAG_URL`: direct link to DAG in Airflow UI (optional).
- `AIRFLOW_BASE_URL`: base URL of Airflow UI for constructing links (e.g., `https://airflow.example.com`).

Cloud/Connectors

- BigQuery: ADC (`GOOGLE_APPLICATION_CREDENTIALS` or gcloud auth).

Connections via config

- You define env var names in the config:
  - `connections.source_env_var` and `connections.target_env_var` are the names to read.
  - Example: set `SRC_URI` and `TGT_URI` in your environment.

Soda

- `SODA_CONFIG` optional default configuration file path when not provided in route.
