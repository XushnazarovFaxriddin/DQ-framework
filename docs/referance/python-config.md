# Python Config Reference

Python configs are loaded by `src/compiler/loader.py` via one of:

- `build(vars)` → returns mapping
- `CONFIG` mapping or callable yielding a mapping

Returned mapping must validate against the YAML schema (`ConfigModel`).

Example

```py
def build(vars):
    env = vars.get("env", "dev")
    return {
        "connections": {
            "source_env_var": "SRC_URI",
            "target_env_var": "TGT_URI",
            "source_type": "postgres",
            "target_type": "bigquery",
        },
        "tables": [
            {
                "name": f"orders_{env}",
                "source": {"table": "public.orders"},
                "target": {"table": "`project.ds.orders`"},
                "checks": [
                    {"type": "row_count"},
                    {"type": "hash_diff", "include": ["id", "amount"]},
                ],
            }
        ],
    }
```

Notes

- Python gives you programmatic control (loops/functions) to generate many tables/checks.
- `normalize_config` applies CLI overrides and produces `vars_map` used by the planner.

