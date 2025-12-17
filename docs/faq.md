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

How do I pass secrets like DB credentials?

- Use environment variables and reference them in config via `connections.source_env_var` and `connections.target_env_var`.

How do I use templating in table definitions?

- Use Jinja2 syntax in table/query definitions. Pass variables via `--vars` or environment.

How do I customize logging?

- Modify logging configuration in `src/utils/logger.py` or set log level via env var `DQF_LOG_LEVEL`.

Where can I find detailed references for config schema, CLI, env vars, and Python configs?

- See the reference docs: YAML Schema, CLI Reference, Environment Variables, Python Config Reference.

How do I contribute?

- Fork the repo, make changes, and submit a pull request. Follow the contribution guidelines in the README.

Have more questions?

- Check the official documentation or open an issue on the Bitbucket repo.