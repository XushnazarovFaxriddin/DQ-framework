# CSV (Local) Connector

Module: `src/connectors/csv_local.py`

Capabilities

- DuckDB in‑memory SQL over `read_csv_auto('<path>')`
- `render_select_sql` from `QueryCfg` (table path) or verbatim `query`
- Deterministic hashing via DuckDB `md5` UDF (digest extension or custom)

URI

- `csv://` (scheme informational); actual path comes from `QueryCfg.table`

Hashing (`HashingCfg`)

- `double_md5` and `md5_row` supported
- `sha256_row` not supported

Example (YAML)

```yaml
connections:
    source_env_var: CSV_SOURCE_CONN
    target_env_var: CSV_TARGET_CONN
    source_type: csv
    target_type: csv

tables:
    - name: sample_csv_table
        source:
            table: data/source.csv
        target:
            table: data/target.csv
```

