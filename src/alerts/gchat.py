"""Google Chat alert sender (supports text and card payloads)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import requests

from src.render.gchat_cards import (
    build_run_card,
    context_lines,
    _has_extra_in_target,
    _get_extra_in_target_count,
    _get_diff_percentage_for_check,
    _format_percentage,
    _get_airflow_info,
    _build_airflow_log_url,
    _build_airflow_dag_url,
)
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

        # Check for critical extra_in_target issues
        extra_in_target_checks = [c for c in result.checks if _has_extra_in_target(c)]
        if extra_in_target_checks:
            lines.append("")
            lines.append("🚨 CRITICAL DATA INTEGRITY ALERT 🚨")
            lines.append("Target database contains records that DO NOT EXIST in source!")
            for check in extra_in_target_checks[:5]:
                count = _get_extra_in_target_count(check)
                lines.append(f"  - {check.table}/{check.check_type}: {count} extra records in target")
            lines.append("")

        for check in result.checks[:max_checks]:
            severity_note = ""
            if check.status == "FAIL":
                severity_note = f" [{check.severity or 'WARNING'}]"
            line = f"{check.table}/{check.check_type}: {check.status}{severity_note}"

            # Add diff percentage for failed checks
            if check.status == "FAIL":
                diff_pct = _get_diff_percentage_for_check(check)
                if diff_pct is not None and diff_pct > 0:
                    line += f" (diff: {_format_percentage(diff_pct)})"

            csv_links = csv_links_for_check(check)
            if csv_links:
                preview = "; ".join(csv_links[:2])
                line += f" | Mismatch CSVs: {preview}"
            lines.append(line)

        # Add Airflow info at the end
        airflow_info = _get_airflow_info()
        if any(airflow_info.values()):
            lines.append("")
            lines.append("📊 Airflow Run Info:")
            if airflow_info.get("dag_id"):
                lines.append(f"  DAG: {airflow_info['dag_id']}")
            if airflow_info.get("task_id"):
                lines.append(f"  Task: {airflow_info['task_id']}")
            if airflow_info.get("dag_run_id"):
                lines.append(f"  Run ID: {airflow_info['dag_run_id']}")

            log_url = _build_airflow_log_url(airflow_info)
            dag_url = _build_airflow_dag_url(airflow_info)
            if log_url:
                lines.append(f"  📋 Task Log: {log_url}")
            if dag_url:
                lines.append(f"  🔗 DAG: {dag_url}")

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
