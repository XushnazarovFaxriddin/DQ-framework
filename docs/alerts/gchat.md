# Google Chat Alerts

Module: `src/alerts/gchat.py`

Modes

- `text`: compact plain text summary
- `card`: rich card with structured widgets

Route config (YAML)

```
alerts:
  routes:
    - kind: gchat
      mode: card            # or text
      webhook: https://chat.googleapis.com/...
      send_all_checks: false
```

Webhook resolution

- Use `webhook:` in route or `GCHAT_DQ_WEBHOOK` env var

Payloads

- Text: title + first N checks (default 50)
- Card: built via `render/gchat_cards.py` with status summary and items

