# Example: Oracle → BigQuery

Config: align with `config/yaml/sw_res_header_test.yaml` (pattern).

Highlights

- Connections declare `source_type: oracle`, `target_type: bigquery`.
- Google Chat alert route with `mode: card`.
- Aggregations over date fields with tolerances.

Run

```
dqf --config-file sw_res_header_test --filetype yaml --vars env=prod run_label=testing
```

