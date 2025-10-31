# Logging

DQF emits structured JSON logs using a custom formatter (`src/utils/logger.py`).

Format

```
{
  "ts": "2025-01-01T00:00:00Z",
  "run_id": "...",
  "level": "INFO",
  "event": "check.finish",
  ... additional fields ...
}
```

Usage in code

- `log(event, **fields)` for global structured logging.
- `ContextLogger(table=..., check=...)` to bind context and emit scoped events.

Env vars

- `DQF_RUN_ID`: optional override for run id.
- `DQF_LOG_LEVEL`: default `INFO`.

Typical events

- `main.start`, `main.finish`.
- `plan.build.start`, `execution.start`, `table.submitted`.
- `check.start`, `check.finish`, `check.error`.

