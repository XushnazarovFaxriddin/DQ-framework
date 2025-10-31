# Templating & Variables

Planner renders `QueryCfg` fields with Jinja2 when they contain `{{ ... }}`.

Available variables

- `env`, `run_label` from CLI `--vars` (or `--env`, `--run_label`).
- Partition context: `partition_start_iso`, `partition_end_iso` when partitions enabled.
- All additional `--vars` items are available.

Example

```
source:
  table: SEAWARE.RES_HEADER
target:
  query: |
    SELECT * FROM prod-shore.nbx_parse.hvtb_parse_sw_rpl_res_header
    WHERE last_updated_at >= TIMESTAMP("{{ partition_start_iso }}")
      AND last_updated_at <  TIMESTAMP("{{ partition_end_iso }}")
```

CLI

```
dqf --config-file sw_res_header_test --filetype yaml --vars env=prod run_label=batch1 hours_ago=2
```

