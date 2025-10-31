# Example: CSV and GCS Parquet

Local CSV vs GCS Parquet using DuckDB connectors.

Skeleton config

```
connections:
  source_env_var: SRC_URI   # csv://
  target_env_var: TGT_URI   # gcs+parquet://
  source_type: csv
  target_type: gcs_parquet

tables:
  - name: demo.files
    source: { table: data/source.csv }
    target: { table: gs://bucket/path/data.parquet }
    checks:
      - type: row_count
      - type: hash_diff
        include: [id, email]
```

Set env

```
SRC_URI=csv://
TGT_URI=gcs+parquet://
```

