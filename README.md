# DQ Framework

Config-driven, pluggable data quality runner with first-class support for SQL engines, file-based data sources, and alerting.

## Quickstart

```bash
# Install dependencies
uv sync

# Provide connection URIs for source/target
export SRC_URI="csv://"  # or postgres://user:pass@host:5432/db
export TGT_URI="csv://"

# Run a configuration
uv run -m src.main \
  --filetype=yaml \
  --config-file=config/yaml/hello_world.yaml \
  --env=prod \
  --run_label=nightly_2025-09-09 \
  --concurrency=4 \
  --concurrency_checks=2 \
  --max_rows_preview=1000
```

Structured JSON logs are emitted to stdout and summarized at the end of the run. A non-zero exit code indicates that at least one check failed.

## Configuration

Each run is defined by a config file (YAML or Python). Both styles share the same schema, which is validated by Pydantic and normalized before planning.

### YAML example

```yaml
connections:
  source_env_var: SRC_URI
  target_env_var: TGT_URI
  source_type: csv
  target_type: csv

defaults:
  hashing:
    algorithm: double_md5
    delimiter: "|"
    null_token: "<NULL>"
    case: lower

planning:
  partitions:
    mode: range
    start: 2024-01-01T00:00:00Z
    end: 2024-01-02T00:00:00Z

alerts:
  routes:
    - kind: gchat
      mode: card
    - kind: email
      to:
        - dq@example.com

tables:
  - name: customers
    source:
      table: /data/customers.csv
    target:
      table: /data/customers.csv
    join_keys:
      source: [id]
      target: [id]
    checks:
      - type: row_count
        order_by: [id]
      - type: hash_diff
        include: [id, email, country]
```

### Python example

```python
def build(vars: dict) -> dict:
    env = vars.get("env", "dev")
    base_path = f"/mnt/{env}"
    return {
        "connections": {
            "source_env_var": "SRC_URI",
            "target_env_var": "TGT_URI",
        },
        "tables": [
            {
                "name": "orders",
                "source": {"table": f"{base_path}/orders_{env}.csv"},
                "target": {"table": f"{base_path}/orders_{env}.csv"},
                "join_keys": {"source": ["order_id"], "target": ["order_id"]},
                "checks": [
                    {
                        "type": "join_rowdiff",
                        "include": ["order_id", "status", "total"],
                        "order_by": ["order_id"],
                    }
                ],
            }
        ],
    }
```

### CLI flags and overrides

* `--vars` accepts space or comma separated `key=value` pairs.
* Dedicated flags (`--env`, `--run_label`, `--concurrency`, etc.) override values supplied by `--vars`.
* `--alerts` can override routing at runtime, e.g. `--alerts gchat:webhook=https://hook email:to=ops@example.com`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `SRC_URI`, `TGT_URI` | Connection URIs read via `connections.source_env_var` / `target_env_var` |
| `GCHAT_DQ_WEBHOOK` | Default webhook for Google Chat alerts |
| `DQ_EMAILS` | Fallback recipient list for email alerts (comma separated) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_STARTTLS` | Email transport configuration |
| `DQF_CONCURRENCY`, `DQF_CONCURRENCY_CHECKS`, `DQF_TABLE_TIMEOUT`, `DQF_CHECK_TIMEOUT`, `DQF_MAX_ROWS_PREVIEW` | Defaults for CLI concurrency/timeouts |
| `DQF_LOG_LEVEL` | Logging level (INFO by default) |

## Docker

Build and run inside Docker:

```bash
docker build -t dqf .
docker run --rm \
  -e SRC_URI="csv://" \
  -e TGT_URI="csv://" \
  -e GCHAT_DQ_WEBHOOK="https://chat.googleapis.com/..." \
  -v $(pwd)/config:/app/config \
  dqf \
  uv run -m src.main --filetype=yaml --config-file=/app/config/yaml/hello_world.yaml --env=prod --run_label=daily
```

## Airflow (KubernetesPodOperator)

```python
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator

run_dq = KubernetesPodOperator(
    task_id="dq_customers",
    name="dq-customers",
    namespace="dq",
    image="ghcr.io/your-org/dqf:latest",
    env_vars={
        "SRC_URI": "postgresql+psycopg2://...",
        "TGT_URI": "bigquery://project/dataset",
        "GCHAT_DQ_WEBHOOK": "https://chat.googleapis.com/...",
    },
    cmds=[
        "uv",
        "run",
        "-m",
        "src.main",
        "--filetype=yaml",
        "--config-file=/app/config/yaml/customers.yaml",
        "--env=prod",
        "--run_label={{ ds }}",
        "--concurrency=4",
        "--concurrency_checks=2",
    ],
)
```

## Development

* Format: `uv run ruff format && uv run ruff check`
* Type checking: `uv run mypy`
* Tests: `uv run pytest`

## Logging

All logs use a JSON envelope with stable fields such as `event`, `level`, `env`, `run_label`, `table`, and `check_type`. Attach your favorite log shipper or parse directly in BigQuery/Splunk for historical run analysis.
