# Soda (Adapter)

Purpose: execute Soda scans using configuration + checks provided in the check config.

How it works (`src/checks/expectations/soda_adapter.py`):

- Loads Soda configuration (YAML) from `config_file` or `config_yaml` (or `SODA_CONFIG` env)
- Sets data source name (`data_source`)
- Injects variables (framework `vars_map` + `variables` + `'on'` side)
- Loads checks from `checks_file` or `checks_yaml`
- Executes scan and summarizes failures

Config (first `rules` item is used)

```yaml
type: soda_checks
rules:
  - 'on': source | target               # YAML: quote 'on'
    config_file: path/to/config.yml     # or config_yaml: "..."
    data_source: my_source
    checks_file: path/to/checks.yml     # or checks_yaml: "..."
    variables: { key: value }
```

Example

```yaml
- type: soda_checks
  rules:
    - config_file: soda/config.yml
      data_source: dw
      checks_file: soda/checks.yml
      variables: { table_name: "{{ table_cfg.name }}" }
      'on': source
```

Soda configuration example (`config.yml`):

```yaml
data_sources:
  my_source:
    type: sql
    connection:
      type: postgres
      host: "{{ SOURCE_HOST }}"
      port: 5432
      database: my_db
      username: "{{ SOURCE_USER }}"
      password: "{{ SOURCE_PASSWORD }}"
``` 
Soda checks example (`checks.yml`):

```yaml
checks:
  - row_count > 0
  - column { name: email }
      missing_count < 10
      invalid_count < 5
```

Soda documents:
- [Soda Docs](https://docs.soda.io/)
- [Getting Started with Soda SQL](https://docs.soda.io/soda-sql/getting-started/)
- [Defining Checks](https://docs.soda.io/soda-sql/defining-checks/)
- [Data Source Configuration](https://docs.soda.io/soda-sql/data-source-configuration/)
- [Using Variables](https://docs.soda.io/soda-sql/using-variables/)
- [Soda Core GitHub](https://github.com/sodadata/soda-core)

Details output

```
details: { failures: [ ... ], failed: <int>, data_source: <str> }
```

Notes

- Requires Soda libs; adapter imports module at runtime.
- Always quote `'on'` in YAML. See Reference → YAML Quoting Rules.

