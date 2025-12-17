# Planner & Partitions

Planner responsibilities (`src/compiler/planner.py`)

- Build a runnable plan from `ConfigModel`.
- Fan‑out over partition windows (optional).
- Render `QueryCfg` with Jinja2 templates.
- Execute table units with per‑table/per‑check timeouts.

Templating context (Jinja2)

- `env`, `run_label` (from `--vars`).
- `partition_start_iso`, `partition_end_iso` when partitions are enabled.
- All CLI vars are available as template variables.

Partitions (PlanningCfg)

```yaml
planning:
  partitions:
    mode: none | rolling_days | rolling_hours | range
    window: <int>                # for rolling modes
    start: <iso8601>             # for range
    end:   <iso8601>
```

Execution knobs (from vars/CLI)

- `concurrency`, `concurrency_checks`.
- `table_timeout_sec`, `check_timeout_sec`.
- `max_rows_preview` (caps preview size for rowdiff/attachments).

