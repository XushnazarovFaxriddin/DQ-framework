# Concurrency & Timeouts

Execution parameters can be provided via CLI or `--vars` and applied in normalization.

Parameters

- `concurrency`: max parallel tables (default `DQF_CONCURRENCY` or 4)
- `concurrency_checks`: max parallel checks per table (default `DQF_CONCURRENCY_CHECKS` or 1)
- `table_timeout_sec`: optional per‑table timeout (env `DQF_TABLE_TIMEOUT`)
- `check_timeout_sec`: optional per‑check timeout (env `DQF_CHECK_TIMEOUT`)
- `max_rows_preview`: cap diff preview sizes (default `DQF_MAX_ROWS_PREVIEW` or 1000)

Example

```
dqf --config-file sw_oracle_vs_bq --filetype yaml \
    --concurrency 8 --concurrency_checks 2 \
    --table_timeout_sec 600 --check_timeout_sec 120 \
    --max_rows_preview 2000
```

