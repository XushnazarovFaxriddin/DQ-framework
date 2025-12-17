# DQF — Data Quality Framework

DQF is a config‑driven, pluggable data quality framework for comparing and validating data across systems (e.g., Oracle → BigQuery, Postgres → BigQuery, CSV/GCS → SQL). It provides built‑in checks, connector plugins, partitioned planning, and alerting.

What you get

- Config as code: YAML or Python
- Pluggable connectors and checks
- Deterministic hashing parity across engines
- Parallel execution with timeouts
- Google Chat and Email alerts with previews

Quick links

- Getting Started → Install, Quickstart
- Concepts → Config model, planner, hashing, results, registry
- Checks → Row count, hash diff, join rowdiff, domain, freshness, aggregations, custom SQL, GE, Soda
- Connectors → BigQuery, Postgres, Oracle, MSSQL, Snowflake, CSV, GCS CSV/Parquet
- How‑To → Docker, Airflow, templating, env, concurrency/timeouts, reporting

