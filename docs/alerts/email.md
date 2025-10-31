# Email Alerts (SMTP)

Module: `src/alerts/email.py`

Behavior

- Builds summary text and markdown table
- Attaches CSV previews for diff details when present
- Sends via SMTP with optional STARTTLS and auth

Route config (YAML)

```
alerts:
  routes:
    - kind: email
      to: ["user@example.com", "dq@corp.com"]
```

Recipient resolution

- Use route `to:` or fallback to `DQ_EMAILS` env (comma‑separated)

SMTP envs

- `SMTP_HOST` (required), `SMTP_PORT` (default 25)
- `SMTP_FROM` (default `dqf@localhost`), `SMTP_USER`, `SMTP_PASS`
- `SMTP_STARTTLS=true` to enable
- Optional `DQF_EMAIL_SUBJECT` prefix

