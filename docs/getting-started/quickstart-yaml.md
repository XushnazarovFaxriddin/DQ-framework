# Quickstart (YAML)

DQF runs from a YAML config defining connections, tables, and checks.

1) Set connection URIs via environment variables referenced by config
2) Create a YAML config
3) Run the CLI

Minimal example

```
# config/yaml/hello_world.yaml
connections:
  source_env_var: SRC_URI     # e.g., postgres://user:pass@host:5432/db
  target_env_var: TGT_URI     # e.g., bigquery://
  source_type: postgres       # optional
  target_type: bigquery

tables:
  - name: demo.users
    source: { table: public.users }
    target: { table: `project.dataset.users` }
    checks:
      - type: row_count
      - type: hash_diff
        include: [id, email]

defaults:
  hashing: { algorithm: double_md5, null_token: "", delimiter: "|", case: upper }
```

Run

```
dqf --config-file hello_world --filetype yaml --vars env=dev run_label=local
```

YAML quoting note (important)

- YAML 1.1 treats bare words like `on` as booleans. When you need to select a side for checks that support it, always quote the key `'on'`:

```
- type: freshness
  'on': target
  column: last_updated_at
  max_lag_minutes: 60
```

