# Example: MSSQL → BigQuery (with Rowdiff)

Config: similar to `config/yaml/mxp_prod_replica_test.yaml`.

Highlights

- Source `mssql`, target `bigquery`.
- `row_count` and `join_rowdiff` with explicit join keys.

Run

```
dqf --config-file mxp_prod_replica_test --filetype yaml --vars env=prod run_label=testing
```

