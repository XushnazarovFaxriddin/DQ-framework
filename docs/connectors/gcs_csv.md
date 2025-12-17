# GCS CSV Connector

Module: `src/connectors/gcs_csv.py`

Capabilities

- DuckDB SQL over `read_csv_auto('gs://...')` with `httpfs` extension
- `render_select_sql` from `QueryCfg` or verbatim `query`
- Deterministic hashing via DuckDB `md5`

URI

- `gcs+csv://` (scheme informational); actual GCS path comes from `QueryCfg.table`

Hashing (`HashingCfg`)

- `double_md5` and `md5_row` supported
- `sha256_row` not supported

Auth

- Ensure DuckDB `httpfs` can authenticate to GCS in your environment

