"""
Google Chat Card renderer:
- Builds a compact card summarizing run status and failed checks.
- Use with alerts.gchat when route.mode == "card".
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, List, Mapping, Optional

from src.render.mismatch_links import csv_links_for_check
from src.runtime.results import CheckResult, RunResult


def _format_csv_links(links: List[str]) -> str:
    if not links:
        return ""
    items = [f'<a href="{uri}">Download mismatch CSV</a>' for uri in links[:2]]
    return "<br>".join(items)


def _build_csv_widget(links: List[str]) -> Dict[str, Any]:
    if not links:
        return {}
    uri = _console_uri(links[0])
    plural = "s" if len(links) > 1 else ""
    label = f"Mismatch CSV{plural}"
    if len(links) > 1:
        label += f" ({len(links)} total)"
    return {
        "buttonList": {
            "buttons": [
                {
                    "text": label,
                    "onClick": {"openLink": {"url": uri}},
                }
            ]
        }
    }


def _console_uri(uri: str) -> str:
    """
    Convert a mismatch CSV URI into a Cloud Console object URL when possible.
    Falls back to the original URI if required env vars are missing.
    """
    bucket = os.getenv("DQF_RESULTS_BUCKET")
    base_path = os.getenv("DQF_RESULTS_BASE_PATH", "")
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
    try:
        file_name = uri.rsplit("/", 1)[-1]
    except Exception:
        file_name = None
    if bucket and file_name:
        base = base_path.strip("/ ")
        middle = f"{base}/" if base else ""
        if project:
            return (
                "https://console.cloud.google.com/storage/browser/_details/"
                f"{bucket}/{middle}{file_name};tab=live_object?project={project}"
            )
        return (
            "https://console.cloud.google.com/storage/browser/_details/"
            f"{bucket}/{middle}{file_name}"
        )
    return uri


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    text = f"{value:.2f}"
    return text.rstrip("0").rstrip(".")


def _first_available(details: Mapping[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in details and details[key] is not None:
            return details[key]
    return None


def _metric_summary(details: Mapping[str, Any]) -> Optional[str]:
    source_raw = _first_available(details, ["source_count", "source_value", "source"])
    target_raw = _first_available(details, ["target_count", "target_value", "target"])
    source = _to_float(source_raw)
    target = _to_float(target_raw)
    segments: List[str] = []
    if source is not None:
        segments.append(f"source={_format_number(source)}")
    elif source_raw is not None:
        segments.append(f"source={source_raw}")
    if target is not None:
        segments.append(f"target={_format_number(target)}")
    elif target_raw is not None:
        segments.append(f"target={target_raw}")
    if source is not None and target is not None:
        diff = source - target
        segments.append(f"diff={_format_number(diff)}")
    reason = details.get("reason")
    if isinstance(reason, str) and reason and reason not in {"threshold", "missing_source", "missing_target"}:
        segments.append(f"reason={reason}")
    return " | ".join(segments) if segments else None


_CONFIG_FIELDS: List[tuple[str, str]] = [
    ("on", "on"),
    ("tolerance_pct", "tol_pct"),
    ("tolerance_abs", "tol_abs"),
    ("sample_mode", "sample_mode"),
    ("chunk_size", "chunk_size"),
    ("id_column", "id"),
    ("id_column_source", "src_id"),
    ("id_column_target", "tgt_id"),
]


def _format_config_summary(details: Mapping[str, Any]) -> Optional[str]:
    candidates: List[Mapping[str, Any]] = []
    config = details.get("config_summary") if isinstance(details, Mapping) else None
    if isinstance(config, Mapping):
        candidates.append(config)
    config = details.get("config") if isinstance(details, Mapping) else None
    if isinstance(config, Mapping):
        candidates.append(config)
    candidates.append(details)

    for candidate in candidates:
        segments: List[str] = []
        for key, label in _CONFIG_FIELDS:
            value = candidate.get(key)
            if value is None:
                continue
            if isinstance(value, float):
                value = _format_number(value)
            segments.append(f"{label}={value}")
            if len(segments) >= 3:
                break
        if segments:
            return " | ".join(segments)
    return None


def _error_snippet(details: Mapping[str, Any]) -> Optional[str]:
    if not isinstance(details, Mapping):
        return None
    error = details.get("error")
    if not isinstance(error, str) or not error.strip():
        return None
    snippet = error.strip().splitlines()[0]
    if len(snippet) > 200:
        snippet = snippet[:200] + " ..."
    return snippet


def _expand_failure_entries(check: CheckResult, send_only_fails: bool) -> List[Dict[str, Any]]:
    details = check.details if isinstance(check.details, Mapping) else {}
    entries: List[Dict[str, Any]] = []
    is_aggregations = str(check.check_type).endswith("aggregations")
    if is_aggregations and isinstance(details, Mapping):
        rules = details.get("rules", [])
        for idx, rule in enumerate(rules):
            status = "PASS" if bool(rule.get("pass")) else "FAIL"
            if send_only_fails and status != "FAIL":
                continue
            method = rule.get("method") or f"rule_{idx}"
            entries.append(
                {
                    "table": check.table,
                    "check_type": f"{check.check_type}[{method}]",
                    "status": status,
                    "severity": check.severity or ("WARNING" if status == "FAIL" else "INFO"),
                    "metrics": rule if isinstance(rule, Mapping) else {},
                }
            )
        if entries:
            return entries

    status = "PASS" if str(check.status).upper() == "PASS" else (check.status or "FAIL")
    if send_only_fails and status != "FAIL":
        return []
    entries.append(
        {
            "table": check.table,
            "check_type": check.check_type,
            "status": status,
            "severity": check.severity or ("WARNING" if status == "FAIL" else "INFO"),
            "metrics": details,
        }
    )
    return entries


def _shorten_ts(value: str | None) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except Exception:
        return value
    parsed_utc = parsed.astimezone(timezone.utc)
    return parsed_utc.strftime("%Y-%m-%d %H:%M:%S %Z")


def context_lines(context: Mapping[str, Any]) -> List[str]:
    lines: List[str] = []

    def _maybe_add(label: str, key: str) -> None:
        val = context.get(key)
        if val is None:
            return
        text = str(val).strip()
        if not text:
            return
        if key in {"run_start", "run_end"}:
            text = _shorten_ts(text)
        lines.append(f"<b>{label}:</b> {text}")

    _maybe_add("Config File", "config_file")
    _maybe_add("Env", "env")
    _maybe_add("Run Label", "run_label")
    _maybe_add("Started", "run_start")
    _maybe_add("Ended", "run_end")
    return lines


def _build_context_widget(context: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if not context:
        return None
    lines = context_lines(context)
    if not lines:
        return None
    return {"textParagraph": {"text": "<br>".join(lines)}}


def build_run_card(
    result: RunResult,
    *,
    max_items: int = 50,
    send_only_fails: bool = True,
    context: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    failures = [c for c in result.checks if c.status == "FAIL"]

    header = {
        "title": f"DQF Validation Summary - {result.overall_status}",
        "subtitle": (
            f"Failures: {len(failures)} | Total Checks: {len(result.checks)} | "
            f"Severity: {result.overall_severity or 'INFO'}"
        ),
    }

    if not failures:
        return {"cardsV2": [{"card": {"header": header, "sections": []}}]}

    checks = failures if send_only_fails else result.checks
    flat_entries: List[Dict[str, Any]] = []

    for idx, check in enumerate(checks):
        entries = _expand_failure_entries(check, send_only_fails)
        if not entries:
            continue
        csv_links = csv_links_for_check(check)
        for entry in entries:
            entry["csv_links"] = csv_links
            entry["check_index"] = idx
            flat_entries.append(entry)
            if len(flat_entries) >= max_items:
                break
        if len(flat_entries) >= max_items:
            break

    widgets: List[Dict[str, Any]] = []
    links_rendered: set[int] = set()
    previous_table: Optional[str] = None
    context_widget = _build_context_widget(context or {})
    if context_widget:
        widgets.append(context_widget)
        widgets.append({"divider": {}})

    for order, entry in enumerate(flat_entries[:max_items], start=1):
        if previous_table and previous_table != entry["table"]:
            widgets.append({"divider": {}})
        previous_table = entry["table"]

        text_lines = [
            f"<b>#{order}. {entry['table']}</b>",
            f"<b>Check Type:</b> {entry['check_type']}",
            f"<b>Status:</b> {entry['status']}",
            f"<b>Severity:</b> {entry['severity']}",
        ]
        metrics_summary = (
            _metric_summary(entry["metrics"])
            if isinstance(entry["metrics"], Mapping)
            else None
        )
        if metrics_summary:
            text_lines.append(f"<b>Metrics:</b> {metrics_summary}")
        config_summary_line = (
            _format_config_summary(entry["metrics"])
            if isinstance(entry["metrics"], Mapping)
            else None
        )
        if config_summary_line:
            text_lines.append(f"<b>Config:</b> {config_summary_line}")
        error_line = (
            _error_snippet(entry["metrics"])
            if isinstance(entry["metrics"], Mapping)
            else None
        )
        if error_line:
            text_lines.append(f"<b>Error:</b> {error_line}")
        if entry["csv_links"]:
            csv_html = _format_csv_links(entry["csv_links"])
            if csv_html:
                text_lines.append(f"<b>Mismatch CSV:</b><br>{csv_html}")

        widgets.append({"textParagraph": {"text": "<br>".join(text_lines)}})

        check_idx = entry["check_index"]
        if entry["csv_links"] and check_idx not in links_rendered:
            link_widget = _build_csv_widget(entry["csv_links"])
            if link_widget:
                widgets.append(link_widget)
            links_rendered.add(check_idx)

    return {
        "cardsV2": [
            {
                "cardId": "run_summary",
                "card": {
                    "header": header,
                    "sections": [
                        {"header": "Failed Validations", "widgets": widgets}
                    ],
                },
            }
        ]
    }
