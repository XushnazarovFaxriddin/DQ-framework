"""Google Chat alert sender (supports text, card, markdown modes)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests

from src.render.gchat_cards import build_run_card
from src.render.tabular import markdown_summary_table
from src.render.summarize import summarize_run
from src.runtime.registry import register_alert
from src.runtime.results import RunResult


def _resolve_webhook(route: Optional[Dict[str, Any]]) -> Optional[str]:
    """Resolve webhook from route or environment variable."""
    if route and route.get("webhook"):
        return str(route["webhook"])
    return os.getenv("GCHAT_DQ_WEBHOOK")


@register_alert("gchat")
def send_gchat(
    result: RunResult, *, route: Optional[Dict[str, Any]] = None, mode: str = "text"
) -> None:
    """
    Send Google Chat alert message in one of the supported modes:
      - text     → simple line-based summary
      - card     → formatted Google Chat card with structured fields
    """
    webhook = _resolve_webhook(route)
    if not webhook:
        return

    headers = {"Content-Type": "application/json; charset=UTF-8"}
    payload: Dict[str, Any]

    mode = (route.get("mode") if route else mode) or mode
    send_all_checks = bool(route.get("send_all_checks", False))
    mode = str(mode).lower()
    max_checks = 50
    if mode == "card":
        # Fancy card-style visualization (JSON payload with widgets)
        payload = build_run_card(result, max_items=max_checks, send_only_fails=(not send_all_checks))
    else:
        # Simple text list of checks
        title = f"📊 DQF Validation Summary — {result.overall_status}"
        lines = [f"{c.table}/{c.check_type}: {c.status}" for c in result.checks[:max_checks]]
        payload = {"text": title + "\n" + "\n".join(lines)}

    # Send to GChat webhook
    requests.post(webhook, data=json.dumps(payload), headers=headers, timeout=10)
