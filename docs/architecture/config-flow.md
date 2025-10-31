# Config Flow

Loading (`src/compiler/loader.py`)

- YAML: file is read and `${VAR}` placeholders are interpolated from env, then parsed with PyYAML.
- Python: executes `build(vars)` or uses `CONFIG`; returns a mapping.

Validation (`src/compiler/schema.py`)

- Pydantic models validate structure and apply defaults (e.g., `hashing`).

Normalization (`src/compiler/normalizer.py`)

- Applies CLI overrides (concurrency, timeouts, preview limit).
- Merges `alerts` with route overrides from `--alerts`.
- Produces `cfg` (normalized `ConfigModel`) and `vars_map` used by planner.

Context (`src/runtime/context.py`)

- Resolves `source_uri` and `target_uri` from env vars named in `connections`.
- Builds connectors via `src/connectors/factory.py` with scheme → engine mapping.

