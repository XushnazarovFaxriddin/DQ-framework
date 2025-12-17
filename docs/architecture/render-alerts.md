# Render & Alerts

Rendering

- `summarize_run` builds a concise textual overview with counts and failure listings.
- `markdown_summary_table` produces a compact table for chat/email.
  - Aggregations expand per rule (e.g., `aggregations[sum]`).

Alerts dispatcher (`src/alerts/dispatcher.py`)

- Iterates configured `alerts.routes`.
- Resolves recipients/webhook, invokes registered alert handlers.
- Skips when no routes are defined.

Backends

- Google Chat (`gchat`): `mode: text|card`, optional `send_all_checks`.
- Email (`email`): recipients from route or `DQ_EMAILS`, uses SMTP envs.

