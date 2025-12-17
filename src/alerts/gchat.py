"""Google Chat alert sender (supports text and card payloads)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import requests

from src.render.gchat_cards import build_run_card, context_lines
from src.render.mismatch_links import csv_links_for_check
from src.runtime.registry import register_alert
from src.runtime.results import RunResult
from src.utils.logger import log


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
      - text: simple line-based summary
      - card: formatted Google Chat card
    """
    webhook = _resolve_webhook(route)
    if not webhook:
        return

    headers = {"Content-Type": "application/json; charset=UTF-8"}
    payload: Dict[str, Any]

    mode = (route.get("mode") if route else mode) or mode
    context_meta = result.metadata if isinstance(result.metadata, dict) else {}
    send_all_checks = bool(route.get("send_all_checks", False))
    mode = str(mode).lower()
    max_checks = 200
    if mode == "card":
        payload = build_run_card(
            result,
            max_items=max_checks,
            send_only_fails=(not send_all_checks),
            context=context_meta,
        )
    else:
        severity_label = result.overall_severity or "INFO"
        title = f"DQF Validation Summary - {result.overall_status} [{severity_label}]"
        lines: List[str] = []
        context_lines_list = context_lines(context_meta)
        if context_lines_list:
            lines.append("Context: " + "; ".join(context_lines_list))
        for check in result.checks[:max_checks]:
            severity_note = ""
            if check.status == "FAIL":
                severity_note = f" [{check.severity or 'WARNING'}]"
            line = f"{check.table}/{check.check_type}: {check.status}{severity_note}"
            csv_links = csv_links_for_check(check)
            if csv_links:
                preview = "; ".join(csv_links[:2])
                line += f" | Mismatch CSVs: {preview}"
            lines.append(line)
        payload = {"text": title + "\n" + "\n".join(lines)}

    try:
        response = requests.post(
            webhook, data=json.dumps(payload), headers=headers, timeout=10
        )
        if response.status_code >= 400:
            log(
                "alerts.gchat.error",
                level="ERROR",
                status=response.status_code,
                response_text=response.text[:5000],
            )
    except Exception as exc:  # noqa: BLE001
        log(
            "alerts.gchat.error",
            level="ERROR",
            error=str(exc),
        )
