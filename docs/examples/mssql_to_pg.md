# Example: MSSQL → BigQuery (with Rowdiff)

Config: similar to `config/yaml/mxp_prod_replica_test.yaml`.

Highlights

- Source `mssql`, target `bigquery`.
- `row_count` and `join_rowdiff` with explicit join keys.

Run

```
dqf --config-file mxp_prod_replica_test --filetype yaml --vars env=prod run_label=testing
```


Example config
```yaml
connections:
    source_type: mssql
    source_env_var: MXP_MSSQL_CONN
    target_type: bigquery
    target_env_var: PROD_BQ_CONN

alerts:
    - kind: gchat
    - mode: card

tables:
    - name: mxp.customers
        source:
            table: dbo.customers
        target:
            table: analytics.mxp_customers
        checks:
            - type: row_count
            - type: join_rowdiff
                join_keys: [customer_id]
                include: [first_name, last_name, email, phone_number]
```