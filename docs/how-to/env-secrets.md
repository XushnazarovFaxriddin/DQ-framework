# Env & Secrets

Connection URIs are supplied via environment variables whose names are declared in your config’s `connections` block.

Example

```
connections:
  source_env_var: SRC_URI
  target_env_var: TGT_URI
```

Set in your environment or `.env` (loaded by `python-dotenv` in `src/main.py`)

```
SRC_URI=postgres://user:pass@host:5432/db
TGT_URI=bigquery://project.dataset
```

Other secrets

- Google Chat: `GCHAT_DQ_WEBHOOK`
- Email SMTP: `SMTP_*`, `DQ_EMAILS`
- Framework defaults: `DQF_*` envs

Tip: store `.env` next to your config and do not commit it.

