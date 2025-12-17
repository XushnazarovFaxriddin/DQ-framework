# Google Chat Alerts

Module: `src/alerts/gchat.py`

Modes

- `text`: compact plain text summary
- `card`: rich card with structured widgets

Route config (YAML)

```yaml
alerts:
  routes:
    - kind: gchat
      mode: card                # or text
      send_all_checks: false    # optional, default false
```

Webhook resolution

- Use `webhook:` in route or `GCHAT_DQ_WEBHOOK` env var

Payloads

- Text: title + first N checks (default 50)
- Card: built via `render/gchat_cards.py` with status summary and items
- When checks expose `mismatch_csv_uri`, both modes highlight the URI/player so recipients can download the CSV directly instead of inline JSON.
- Severity levels (INFO/WARNING/CRITICAL) are now surfaced in the title/card header and per-check entries so you can prioritize critical mismatches immediately.

