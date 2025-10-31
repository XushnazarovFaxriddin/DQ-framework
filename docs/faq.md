# FAQ

What config formats are supported?

- YAML and Python. Python must return a mapping compatible with `ConfigModel`.

How do I select source vs target in single‑side checks?

- Use the `'on'` key in YAML (quoted). Example: `'on': source`.

How do I add a custom check?

- Implement a class extending `BaseCheck`, annotate with `@register_check("name")`, and ensure the module is importable (optionally via `DQF_EXTRA_CHECKS`).

How do I control concurrency and timeouts?

- Use CLI flags (`--concurrency`, `--concurrency_checks`, `--table_timeout_sec`, `--check_timeout_sec`) or env defaults.

Where do alerts go?

- Configure routes under `alerts:`. Built‑ins: `gchat` and `email`.

