"""Google Chat alert sender."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests

from src.render.gchat_cards import build_run_card
from src.runtime.registry import register_alert
from src.runtime.results import RunResult


def _resolve_webhook(route: Optional[Dict[str, Any]]) -> Optional[str]:
    if route and route.get("webhook"):
        return str(route["webhook"])
    return os.getenv("GCHAT_DQ_WEBHOOK")


@register_alert("gchat")
def send_gchat(
    result: RunResult, *, route: Optional[Dict[str, Any]] = None, mode: str = "text"
) -> None:
    webhook = _resolve_webhook(route)
    if not webhook:
        return

    headers = {"Content-Type": "application/json; charset=UTF-8"}
    payload: Dict[str, Any]

    mode = (route.get("mode") if route else mode) or mode
    mode = str(mode).lower()

    if mode == "card":
        payload = build_run_card(result)
    else:
        title = f"DQF Run — {result.overall_status}"
        lines = [f"{c.table}/{c.check_type}: {c.status}" for c in result.checks[:40]]
        payload = {"text": title + "\n" + "\n".join(lines)}

    requests.post(webhook, data=json.dumps(payload), headers=headers, timeout=10)
