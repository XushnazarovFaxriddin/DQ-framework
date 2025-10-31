# Table of Contents

This page is a guided map of the DQF documentation. Each entry links to a page and explains what you will find there so you can jump straight to the right place.

- Home
  - `docs/index.md` — Product overview, key features, and quick links to the main areas.

- Getting Started
  - `docs/getting-started/install.md` — Installation requirements, project dependencies, and connector notes.
  - `docs/getting-started/quickstart-yaml.md` — Minimal YAML config, CLI run, and YAML quoting note for `'on'`.

- Concepts
  - `docs/concepts/hashing.md` — HashingCfg, algorithms (`double_md5`, `md5_row`, `sha256_row`), parity across engines.
  - `docs/concepts/planner-partitions.md` — Planner responsibilities, Jinja2 templating context, partitions, concurrency knobs.
  - `docs/concepts/results.md` — `CheckResult`/`RunResult` models, summary renderers, preview attachments.
  - `docs/concepts/registry.md` — Connector/check/alert registries, decorators, and plugin loading controls.

- Checks (Validation Types)
  - `docs/checks/row_count.md` — Count comparison with optional ordering per side.
  - `docs/checks/schema_drift.md` — Column presence/type/nullability differences; optional expected set; case sensitivity.
  - `docs/checks/hash_diff.md` — Value parity via deterministic per‑row hashes; alignment patterns and hashing policy.
  - `docs/checks/join_rowdiff.md` — Key‑based row comparison with per‑cell diffs and tolerances; join keys required.
  - `docs/checks/aggregations.md` — Whole‑table aggregates per rule (count/sum/avg/min/max/distinct_count) with tolerances.
  - `docs/checks/group_aggregations.md` — Aggregates per partition key; per‑rule diffs and failure counts.
  - `docs/checks/partitions.md` — Single method compared across all partitions; diff sample and partition counts.
  - `docs/checks/domain.md` — Single‑side value validation (allowed/excluded, regex, ranges, tolerances). Quote `'on'` in YAML.
  - `docs/checks/freshness.md` — Max timestamp lag on a side; normalize to UTC. Quote `'on'` in YAML.
  - `docs/checks/custom_sql.md` — Single/Dual SQL comparisons with numeric/datetime/JSON support and tolerances. Quote `'on'` in YAML.
  - `docs/checks/expectations_ge.md` — GE adapter (Pandas suite or Checkpoint). Quote `'on'` in YAML.
  - `docs/checks/expectations_soda.md` — Soda adapter (config + checks + variables). Quote `'on'` in YAML.

- Connectors
  - `docs/connectors/bigquery.md` — ADC auth, `render_select_sql`, hashing parity (MD5/SHA256), fetch helpers.
  - `docs/connectors/postgres.md` — SQLAlchemy DSN, md5/sha256 via pgcrypto, fetch helpers.
  - `docs/connectors/oracle.md` — SQLAlchemy DSN, `STANDARD_HASH`, information schema columns.
  - `docs/connectors/mssql.md` — `pymssql` DSN parsing, `HASHBYTES`, info schema.
  - `docs/connectors/snowflake.md` — SQLAlchemy, MD5/SHA2 with HEX_ENCODE; driver requirements.
  - `docs/connectors/csv.md` — DuckDB over local CSV, digest/UDR for md5, limitations.
  - `docs/connectors/gcs_csv.md` — DuckDB `httpfs` + CSV on GCS.
  - `docs/connectors/gcs_parquet.md` — DuckDB `httpfs` + Parquet on GCS.
  - `docs/connectors/airtable.md` — Stub placeholder.
  - `docs/connectors/rest_api.md` — Stub placeholder.

- Alerts
  - `docs/alerts/gchat.md` — Text/card modes, webhook resolution, payload behavior.
  - `docs/alerts/email.md` — SMTP sending, previews as CSV attachments, recipients handling.

- How‑To Guides
  - `docs/how-to/run-docker.md` — Build and run the Docker image with mounted configs and env vars.
  - `docs/how-to/airflow.md` — Run via DockerOperator or BashOperator with environment injection.
  - `docs/how-to/env-secrets.md` — How to wire connection URIs via env vars and `.env`.
  - `docs/how-to/templating.md` — Using Jinja2 variables and partition window parameters.
  - `docs/how-to/concurrency-timeouts.md` — CLI/env controls for parallelism, timeouts, and preview size.
  - `docs/how-to/results-reporting.md` — Rendering summaries and markdown tables; alert options.

- Reference
  - `docs/reference/cli.md` — CLI arguments, examples, and behavior.
  - `docs/reference/yaml-schema.md` — Full config shape for `ConfigModel` and check‑specific fields.
  - `docs/reference/python-config.md` — Python config pattern with `build(vars)` and validation.
  - `docs/reference/env-vars.md` — Framework defaults, alert envs, connector/auth envs.
  - `docs/reference/logging.md` — Structured JSON logging and event taxonomy.
  - `docs/reference/yaml-quirks.md` — YAML 1.1 boolean pitfalls; always quote `'on'` in YAML.

- Architecture
  - `docs/architecture/overview.md` — End‑to‑end pipeline from CLI → loader → planner → execution → alerts.
  - `docs/architecture/config-flow.md` — Loader, schema validation, normalization, context building.
  - `docs/architecture/planner-execution.md` — Partition windows, thread pools, timeouts, order/limits.
  - `docs/architecture/render-alerts.md` — Summary/table renderers and dispatcher behavior.

- Examples
  - `docs/examples/oracle_to_bq.md` — Oracle → BigQuery aggregation check patterns with card alerts.
  - `docs/examples/mssql_to_pg.md` — MSSQL → BigQuery row_count + join_rowdiff.
  - `docs/examples/csv_gcs.md` — Local CSV vs GCS Parquet using DuckDB connectors.

- Troubleshooting & FAQ
  - `docs/troubleshooting.md` — Common issues (YAML quoting, auth, drivers, hashing parity, regex differences).
  - `docs/faq.md` — Frequently‑asked questions (formats, custom checks, controls, alerts).

- Additional Material
  - `docs/executive_overview.md` — High‑level executive summary of the framework and its impact.
