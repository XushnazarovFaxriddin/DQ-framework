# Architecture Overview

Pipeline

1) CLI parses args (`src/cli_args.py`).
2) Config loaded (YAML/Python) (`src/compiler/loader.py`).
3) Config validated (`ConfigModel`) and normalized (`src/compiler/normalizer.py`).
4) Plugins registered (`src/runtime/registry.py` → `register_all()`).
5) Plan built with templating and partitions (`src/compiler/planner.py`).
6) Execution with concurrency and timeouts (thread pools, per‑check table units).
7) Results summarized and alerts dispatched.

Packages

- `src/checks`: built‑in checks and adapters.
- `src/connectors`: data source/target connectors.
- `src/compiler`: schema, loader, normalizer, planner.
- `src/runtime`: registry, context, results.
- `src/alerts`: alert backends.
- `src/render`: formatting for summaries and cards.

