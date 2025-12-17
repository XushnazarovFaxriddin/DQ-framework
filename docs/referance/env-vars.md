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
