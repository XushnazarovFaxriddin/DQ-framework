"""
Google Chat alert sender with text or card mode.
- Reads webhook from env: GCHAT_DQ_WEBHOOK
- If mode == "card", builds card JSON via render.gchat_cards.
"""

import json
import os
from typing import Any, Dict, Optional
import requests

from src.runtime.results import RunResult
from src.runtime.registry import register_alert
from src.render.gchat_cards import build_run_card


@register_alert("gchat")
def send_gchat(result: RunResult, *, route: Optional[Dict[str, Any]] = None, mode: str = "text") -> None:
    webhook = os.getenv("GCHAT_DQ_WEBHOOK")
    if not webhook:
        return

    headers = {"Content-Type": "application/json; charset=UTF-8"}

    if mode == "card":
        payload = build_run_card(result)
        requests.post(webhook, data=json.dumps(payload), headers=headers)
        return

    # default text mode
    title = f"DQF Run — {result.overall_status}"
    lines = []
    for c in result.checks[:40]:
        lines.append(f"{c.table}/{c.check_type}: {c.status}")
    payload = {"text": title + "\n" + "\n".join(lines)}
    requests.post(webhook, data=json.dumps(payload), headers=headers)
