# BigQuery Connector

Module: `src/connectors/bigquery.py`

Capabilities

- Execute SQL using `google-cloud-bigquery` client
- Render `SELECT` from `QueryCfg` or use provided `query`
- Deterministic hashing parity (MD5/SHA256) with `LOWER(TO_HEX(...))`
- Fetch helpers: `fetch_df`, `fetch_scalar`, `fetch_column`

URI / Auth

- URI scheme: `bigquery://` (value not used for auth; ADC is used)
- Authenticate using Google ADC (e.g., `GOOGLE_APPLICATION_CREDENTIALS`)

Hashing (`HashingCfg`)

- `double_md5`: LOWER(TO_HEX(MD5(TO_BYTES(CONCAT(h1,'|',h2,...))))) where `hi` is per‑token md5 hex
- `md5_row`: LOWER(TO_HEX(MD5(TO_BYTES(CONCAT(tokens...)))))
- `sha256_row`: LOWER(TO_HEX(SHA256(TO_BYTES(CONCAT(tokens...)))))

Example (YAML)

```yaml
connections:
  source_env_var: PG_CONN
  source_type: postgres
  target_env_var: BQ_CONN
  target_type: bigquery
```

Notes

- `render_select_sql`: if `query` is set, it is used verbatim; otherwise builds `SELECT <select|*> FROM <table>`
- `render_count_sql`: wraps as `SELECT COUNT(*) AS c FROM (<inner>)`

