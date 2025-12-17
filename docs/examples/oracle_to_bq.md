# Example: Oracle → BigQuery

Config: align with `config/yaml/sw_res_header_test.yaml` (pattern).

Highlights

- Connections declare `source_type: oracle`, `target_type: bigquery`.
- Google Chat alert route with `mode: card`.
- Aggregations over date fields with tolerances.

Run

```sh
dqf --config-file sw_res_header_test --filetype yaml --vars env=prod run_label=testing
```

Example config
```yaml
connections:
  source_env_var: PROD_ORA_SW_CONN_STR
  source_type: oracle
  target_env_var: PROD_BQ_ALL_CONN_STR
  target_type: bigquery

alerts:
  routes:
    - kind: gchat
      mode: card # card or text or markdown

tables:
  - name: RES_HEADER_VALIDATION
    source:
      table: SEAWARE.RES_HEADER
      # query: |
      #   SELECT * FROM SEAWARE.RES_HEADER
      #   WHERE LAST_UPDATED_AT < SYSDATE - ({{hours_ago}}/24)
    target:
      table: prod-shore.nbx_parse.hvtb_parse_sw_rpl_res_header
    checks:
      - type: aggregations
        tolerance_abs: 10             # absolute tolerance: allow up to 10 units or 10 minutes difference
        tolerance_pct: 5.0 # percentage tolerance: allow up to 5% difference
        rules:
          - method: count
            source_col: RES_ID
            target_column: res_id
          - method: distinct_count # Distinct count <column>
            source_col: "RES_ID"
            target_column: "res_id"
          - method: max
            source_col: "CONFIRMATION_DATE"
            target_col: "confirmation_date"
```