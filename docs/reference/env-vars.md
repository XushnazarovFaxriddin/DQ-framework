# Environment Variables

Framework

- `DQF_CONCURRENCY`: default for `--concurrency`.
- `DQF_CONCURRENCY_CHECKS`: default for `--concurrency_checks`.
- `DQF_TABLE_TIMEOUT`: default for `--table_timeout_sec`.
- `DQF_CHECK_TIMEOUT`: default for `--check_timeout_sec`.
- `DQF_MAX_ROWS_PREVIEW`: default for `--max_rows_preview`.
- `DQF_DISABLE_CHECKS`: comma‑separated check names to disable.
- `DQF_EXTRA_CHECKS`: comma‑separated module paths to import.

Alerts

- `GCHAT_DQ_WEBHOOK`: webhook for Google Chat backend (if not provided in route).
- `DQ_EMAILS`: default recipient list for email backend when `to:` omitted.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USER`, `SMTP_PASS`, `SMTP_STARTTLS`.
- `DQF_EMAIL_SUBJECT`: subject prefix for email.

Cloud/Connectors

- BigQuery: ADC (`GOOGLE_APPLICATION_CREDENTIALS` or gcloud auth).

Connections via config

- You define env var names in the config:
  - `connections.source_env_var` and `connections.target_env_var` are the names to read.
  - Example: set `SRC_URI` and `TGT_URI` in your environment.

Soda

- `SODA_CONFIG` optional default configuration file path when not provided in route.

