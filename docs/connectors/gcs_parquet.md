# GCS Parquet Connector

Module: `src/connectors/gcs_parquet.py`

Capabilities

- DuckDB SQL over `read_parquet('gs://...')` with `httpfs`/`parquet` extensions
- `render_select_sql` from `QueryCfg` or verbatim `query`
- Deterministic hashing via DuckDB `md5` (custom function when needed)

URI

- `gcs+parquet://` (scheme informational); actual GCS path from `QueryCfg.table`

Hashing (`HashingCfg`)

- `double_md5` and `md5_row` supported

Auth

- Ensure DuckDB `httpfs` can access GCS

