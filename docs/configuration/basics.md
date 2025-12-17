# Configuration Basics

The framework consumes a single YAML file that declares:

- `connections`: the environment variables where connector URIs live.
- `defaults`: thresholds, row limits, and hashing policy.
- `tables`: a list of table definitions, each with `source`/`target` queries and a `checks` list.
- `results_storage`: optional bucket/storage controls (for mismatch CSV export and the new run/check persistence).
- `alerts`: routing to email, GChat, or other notifiers.

```yaml
connections:
  source_env_var: SEAWARE_SRC_BQ
  target_env_var: SEAWARE_TGT_BQ
  source_type: bigquery
  target_type: bigquery

tables:
  - name: SEAWARE.RES_HEADER
    source:
      table: cert-shore-295415.sw_prod.RES_HEADER
    target:
      table: cert-shore-295415.sw_cert.RES_HEADER
    checks:
      - type: row_count
        id_column: RES_ID
        mismatch_sampling:
          mode: chunk
          chunk_size: 100000
          max_scan_chunks: 20
      - type: aggregations
        rules:
          - method: count
            column: "*"
          - method: sum
            column: RES_AMOUNT
```

Every check defines `type` plus any check-specific hints (`rules`, `include`, `time_column`, etc.). See individual check docs for the available fields (e.g., `docs/checks/row_count.md`, `docs/checks/table_stats.md`).

Optional advanced blocks you can add later:
- `mismatch_sampling` + `results_storage.mismatch_csv` for range-level diagnostics and CSV links.
- `adaptive_thresholds` and `severity_rules` for dynamic tolerance and alert severity.
- `results_storage.runs` / `results_storage.checks` to persist normalized outcomes to BigQuery.

Configuration can also be expressed via Python (see `docs/referance/python-config.md`) if you prefer programmatic assembly or templating beyond YAML.
