# Planner & Execution

Planner (`src/compiler/planner.py`)

- Templating: renders `QueryCfg` with Jinja2 when fields contain `{{ ... }}`.
- Partitions: computes windows (`rolling_days`, `rolling_hours`, `range`, or single window).
- TableUnits: each table × window pair becomes an execution unit.

Execution

- Thread pools: tables (`concurrency`) and checks per table (`concurrency_checks`).
- Timeouts: per‑table and per‑check; failures are caught and recorded.
- Results: each check returns `CheckResult`; `RunResult.overall_status` derived from failures.

Order and limits

- Checks may apply `ORDER BY`/`LIMIT` using helpers (`wrap_order_by`, `wrap_order_by_limit`) to keep diffs deterministic and bounded.

