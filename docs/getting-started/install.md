# Install

Requirements

- Python 3.11+
- Access to connector dependencies (e.g., SQLAlchemy drivers, cloud SDKs)

From source (this repo)

```
pip install -e .
```

This uses `pyproject.toml` dependencies, including

- pydantic, pyyaml, jinja2, pandas, requests
- google‑cloud‑bigquery (+ storage, db‑dtypes)
- SQLAlchemy + drivers (psycopg2, oracledb)
- pymssql, duckdb, python‑dateutil

Optional notes

- BigQuery: authenticate via ADC (`GOOGLE_APPLICATION_CREDENTIALS`).
- Oracle: `oracledb` may require Instant Client for thick mode.
- MSSQL: `pymssql` often needs `freetds` on Linux.
