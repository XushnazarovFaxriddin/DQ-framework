# CLI Reference

Entrypoint: `dqf` (`src/main.py`)

Arguments (`src/cli_args.py`)

- `--config-file` (required): path or logical name
  - Bare names resolve to `config/<filetype>/<name>.<filetype>` relative to CWD
- `--filetype` (required): `yaml` | `py`
- `--vars` key=value pairs; space or comma separated
- `--env` convenience; merged into `--vars`
- `--run_label` convenience; merged into `--vars`
- `--alerts` override routing tokens. Format:
  - Start a backend with `kind[:key=value]`, follow with `key=value` pairs
  - Example: `gchat:webhook=https://... mode=card email:to=dq@corp.com`
- `--concurrency` max parallel tables (default env `DQF_CONCURRENCY` or 4)
- `--concurrency_checks` max parallel checks per table (default env `DQF_CONCURRENCY_CHECKS` or 1)
- `--table_timeout_sec` optional per‑table timeout (sec) (env `DQF_TABLE_TIMEOUT`)
- `--check_timeout_sec` optional per‑check timeout (sec) (env `DQF_CHECK_TIMEOUT`)
- `--max_rows_preview` limit for row‑level previews in alerts (default env `DQF_MAX_ROWS_PREVIEW` or 1000)

Examples

```
dqf --config-file hello_world --filetype yaml --vars env=prod run_label=nightly

dqf --config-file sw_oracle_vs_bq --filetype yaml --alerts gchat:mode=card email:to=data@corp

dqf --config-file hello_world --filetype py --concurrency 8 --check_timeout_sec 120
```

Behavior

- Loads config (YAML/Python), validates via `ConfigModel`
- Registers plugins (`register_all`) then builds plan and runs it
- Prints summary and markdown table to logs; raises on FAIL exit

