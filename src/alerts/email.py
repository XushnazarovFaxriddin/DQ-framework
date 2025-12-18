"""
Email alert backend with SMTP and SendGrid support.

Environment Variables:
    SMTP Configuration:
        - SMTP_HOST: SMTP server hostname
        - SMTP_PORT: SMTP server port (default: 587)
        - SMTP_USER: SMTP username for authentication
        - SMTP_PASS: SMTP password for authentication
        - SMTP_FROM: Sender email address
        - SMTP_STARTTLS: Enable STARTTLS (default: true)
        - SMTP_SSL: Use SSL connection (default: false)

    SendGrid Configuration:
        - SENDGRID_API_KEY: SendGrid API key
        - SENDGRID_FROM: Sender email address for SendGrid

    Common:
        - DQF_EMAIL_SUBJECT: Subject prefix for emails
        - DQF_EMAIL_BACKEND: Email backend to use ('smtp' or 'sendgrid', default: 'smtp')
        - DQ_EMAILS: Default recipient list (comma-separated)

    Airflow Integration:
        - AIRFLOW_DAG_ID, AIRFLOW_TASK_ID, AIRFLOW_DAG_RUN_ID, etc.
"""

from __future__ import annotations

import io
import os
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from src.render.mismatch_links import csv_links_for_check
from src.render.summarize import summarize_run
from src.render.tabular import markdown_summary_table
from src.render.gchat_cards import (
    _get_airflow_info,
    _build_airflow_log_url,
    _build_airflow_dag_url,
    _get_diff_percentage_for_check,
    _format_percentage,
    _has_extra_in_target,
    _get_extra_in_target_count,
)
from src.runtime.registry import register_alert
from src.runtime.results import RunResult
from src.utils.logger import log


class EmailBackend(ABC):
    """Abstract base class for email backends."""

    @abstractmethod
    def send(self, to: List[str], subject: str, body_text: str, body_html: str,
             attachments: List[Tuple[str, bytes]]) -> bool:
        """Send email with optional attachments."""
        ...


class SMTPBackend(EmailBackend):
    """SMTP email backend."""

    def __init__(self):
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.user = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASS")
        self.from_addr = os.getenv("SMTP_FROM", "dqf@localhost")
        self.use_starttls = os.getenv("SMTP_STARTTLS", "true").lower() in ("true", "1", "yes")
        self.use_ssl = os.getenv("SMTP_SSL", "false").lower() in ("true", "1", "yes")

        if not self.host:
            raise EnvironmentError("SMTP_HOST environment variable is required for SMTP backend")

    def send(self, to: List[str], subject: str, body_text: str, body_html: str,
             attachments: List[Tuple[str, bytes]]) -> bool:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(to)

        # Attach text and HTML parts
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # Attach files
        for filename, data in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port) as server:
                    if self.use_starttls:
                        server.starttls()
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)

            log("alerts.email.sent", backend="smtp", recipients=len(to))
            return True

        except Exception as exc:
            log("alerts.email.error", level="ERROR", backend="smtp", error=str(exc))
            return False


class SendGridBackend(EmailBackend):
    """SendGrid email backend."""

    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_addr = os.getenv("SENDGRID_FROM") or os.getenv("SMTP_FROM", "dqf@localhost")

        if not self.api_key:
            raise EnvironmentError("SENDGRID_API_KEY environment variable is required for SendGrid backend")

    def send(self, to: List[str], subject: str, body_text: str, body_html: str,
             attachments: List[Tuple[str, bytes]]) -> bool:
        try:
            import base64
            import requests

            # Build SendGrid API payload
            personalizations = [{"to": [{"email": email} for email in to]}]

            content = [
                {"type": "text/plain", "value": body_text},
                {"type": "text/html", "value": body_html},
            ]

            payload: Dict[str, Any] = {
                "personalizations": personalizations,
                "from": {"email": self.from_addr},
                "subject": subject,
                "content": content,
            }

            # Add attachments
            if attachments:
                payload["attachments"] = [
                    {
                        "content": base64.b64encode(data).decode("utf-8"),
                        "filename": filename,
                        "type": "text/csv",
                        "disposition": "attachment",
                    }
                    for filename, data in attachments
                ]

            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )

            if response.status_code in (200, 201, 202):
                log("alerts.email.sent", backend="sendgrid", recipients=len(to))
                return True
            else:
                log(
                    "alerts.email.error",
                    level="ERROR",
                    backend="sendgrid",
                    status_code=response.status_code,
                    response=response.text[:500],
                )
                return False

        except ImportError:
            log("alerts.email.error", level="ERROR", backend="sendgrid", error="requests library required")
            return False
        except Exception as exc:
            log("alerts.email.error", level="ERROR", backend="sendgrid", error=str(exc))
            return False


def _get_email_backend() -> EmailBackend:
    """Get configured email backend."""
    backend_name = os.getenv("DQF_EMAIL_BACKEND", "smtp").lower()

    if backend_name == "sendgrid":
        return SendGridBackend()
    return SMTPBackend()


def _iter_preview_payloads(
    result: RunResult, limit: int = 3
) -> Iterable[Tuple[str, pd.DataFrame]]:
    """Iterate over preview data frames from failed checks."""
    for check in result.checks:
        if check.status != "FAIL":
            continue
        details = check.details or {}
        for key in (
            "missing_on_target",
            "extra_on_target",
            "mismatch_sample",
            "diff_sample",
        ):
            value = details.get(key)
            if isinstance(value, list) and value:
                df = pd.DataFrame(value)
                yield (f"{check.table}_{check.check_type}_{key}", df)
                limit -= 1
                if limit <= 0:
                    return


def _build_attachments(result: RunResult, limit: int = 3) -> List[Tuple[str, bytes]]:
    """Build CSV attachments from preview data."""
    attachments = []
    for name, df in _iter_preview_payloads(result, limit):
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        payload = buffer.getvalue().encode("utf-8")
        attachments.append((f"{name}.csv", payload))
    return attachments


def _build_email_body(result: RunResult) -> Tuple[str, str]:
    """Build plain text and HTML email bodies."""
    severity_label = result.overall_severity or "INFO"

    # Build plain text body
    text_parts = [
        "DQF Validation Report",
        f"Status: {result.overall_status}",
        f"Severity: {severity_label}",
        "",
        summarize_run(result),
        "",
    ]

    # Add critical extra_in_target warning
    extra_checks = [c for c in result.checks if _has_extra_in_target(c)]
    if extra_checks:
        text_parts.append("⚠️ CRITICAL DATA INTEGRITY ALERT")
        text_parts.append("Target database contains records that DO NOT EXIST in source!")
        for check in extra_checks[:5]:
            count = _get_extra_in_target_count(check)
            text_parts.append(f"  - {check.table}/{check.check_type}: {count} extra records")
        text_parts.append("")

    # Add failed checks with diff percentage
    failed_checks = [c for c in result.checks if c.status == "FAIL"]
    if failed_checks:
        text_parts.append("Failed Checks:")
        for check in failed_checks[:20]:
            line = f"  - {check.table}/{check.check_type}"
            diff_pct = _get_diff_percentage_for_check(check)
            if diff_pct is not None and diff_pct > 0:
                line += f" (diff: {_format_percentage(diff_pct)})"
            text_parts.append(line)
        text_parts.append("")

    # Add mismatch CSV links
    mismatch_links = []
    for check in result.checks:
        if check.status == "FAIL":
            for uri in csv_links_for_check(check):
                mismatch_links.append((check.table, check.check_type, uri))

    if mismatch_links:
        text_parts.append("Mismatch CSV Files:")
        for table, check_type, uri in mismatch_links[:10]:
            text_parts.append(f"  - {table}/{check_type}: {uri}")
        text_parts.append("")

    # Add Airflow info
    airflow_info = _get_airflow_info()
    if any(airflow_info.values()):
        text_parts.append("Airflow Run Info:")
        if airflow_info.get("dag_id"):
            text_parts.append(f"  DAG: {airflow_info['dag_id']}")
        if airflow_info.get("task_id"):
            text_parts.append(f"  Task: {airflow_info['task_id']}")
        if airflow_info.get("dag_run_id"):
            text_parts.append(f"  Run ID: {airflow_info['dag_run_id']}")

        log_url = _build_airflow_log_url(airflow_info)
        dag_url = _build_airflow_dag_url(airflow_info)
        if log_url:
            text_parts.append(f"  Task Log: {log_url}")
        if dag_url:
            text_parts.append(f"  DAG URL: {dag_url}")

    body_text = "\n".join(text_parts)

    # Build HTML body
    html_parts = [
        "<html><body>",
        "<h2>DQF Validation Report</h2>",
        f"<p><strong>Status:</strong> {result.overall_status}<br>",
        f"<strong>Severity:</strong> {severity_label}</p>",
        f"<pre>{summarize_run(result)}</pre>",
    ]

    # Add critical warning in HTML
    if extra_checks:
        html_parts.append(
            '<div style="background-color: #ffebee; border-left: 4px solid #f44336; padding: 10px; margin: 10px 0;">'
            '<strong style="color: #c62828;">⚠️ CRITICAL DATA INTEGRITY ALERT</strong><br>'
            'Target database contains records that DO NOT EXIST in source!'
            '<ul>'
        )
        for check in extra_checks[:5]:
            count = _get_extra_in_target_count(check)
            html_parts.append(f"<li>{check.table}/{check.check_type}: {count} extra records</li>")
        html_parts.append("</ul></div>")

    # Add failed checks table with diff percentage
    if failed_checks:
        html_parts.append("<h3>Failed Checks</h3>")
        html_parts.append('<table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">')
        html_parts.append("<tr><th>Table</th><th>Check</th><th>Diff %</th><th>Severity</th></tr>")
        for check in failed_checks[:20]:
            diff_pct = _get_diff_percentage_for_check(check)
            diff_str = _format_percentage(diff_pct) if diff_pct else "N/A"
            severity = check.severity or "WARNING"
            html_parts.append(
                f"<tr><td>{check.table}</td><td>{check.check_type}</td>"
                f"<td>{diff_str}</td><td>{severity}</td></tr>"
            )
        html_parts.append("</table>")

    # Add summary table
    table_md = markdown_summary_table(result, max_rows=30)
    html_parts.append("<h3>Summary</h3>")
    html_parts.append(f"<pre>{table_md}</pre>")

    # Add mismatch CSV links
    if mismatch_links:
        html_parts.append("<h3>Mismatch CSV Files</h3>")
        html_parts.append("<ul>")
        for table, check_type, uri in mismatch_links[:10]:
            html_parts.append(
                f'<li>{table}/{check_type}: <a href="{uri}">Download CSV</a></li>'
            )
        html_parts.append("</ul>")

    # Add Airflow info in HTML
    if any(airflow_info.values()):
        html_parts.append('<div style="background-color: #e3f2fd; padding: 10px; margin: 10px 0;">')
        html_parts.append("<strong>📊 Airflow Run Info</strong><br>")
        if airflow_info.get("dag_id"):
            html_parts.append(f"DAG: {airflow_info['dag_id']}<br>")
        if airflow_info.get("task_id"):
            html_parts.append(f"Task: {airflow_info['task_id']}<br>")
        if airflow_info.get("dag_run_id"):
            html_parts.append(f"Run ID: {airflow_info['dag_run_id']}<br>")

        log_url = _build_airflow_log_url(airflow_info)
        dag_url = _build_airflow_dag_url(airflow_info)
        if log_url:
            html_parts.append(f'<a href="{log_url}">📋 View Task Log</a> ')
        if dag_url:
            html_parts.append(f'<a href="{dag_url}">🔗 View DAG</a>')
        html_parts.append("</div>")

    html_parts.append("</body></html>")
    body_html = "".join(html_parts)

    return body_text, body_html


@register_alert("email")
def send_email(
    result: RunResult,
    *,
    route: Optional[Dict[str, Any]] = None,
    recipients: Optional[List[str]] = None,
) -> None:
    """
    Send email alert with comprehensive report.

    Args:
        result: RunResult from validation
        route: Alert route configuration (optional)
        recipients: List of email addresses (optional, falls back to route or env)
    """
    # Resolve recipients
    if not recipients:
        if route and route.get("to"):
            to_config = route["to"]
            recipients = to_config if isinstance(to_config, list) else [to_config]
        else:
            env_emails = os.getenv("DQ_EMAILS", "")
            recipients = [e.strip() for e in env_emails.split(",") if e.strip()]

    if not recipients:
        log("alerts.email.skipped", reason="no_recipients")
        return

    try:
        backend = _get_email_backend()
    except EnvironmentError as exc:
        log("alerts.email.error", level="ERROR", error=str(exc))
        return

    # Build subject
    subject_prefix = os.getenv("DQF_EMAIL_SUBJECT", "DQF Run Report")
    severity_label = result.overall_severity or "INFO"
    subject = f"{subject_prefix}: [{severity_label}] {result.overall_status}"

    # Add critical indicator to subject if extra_in_target detected
    if any(_has_extra_in_target(c) for c in result.checks):
        subject = f"🚨 CRITICAL - {subject}"

    # Build body
    body_text, body_html = _build_email_body(result)

    # Build attachments
    attachments = _build_attachments(result)

    # Send email
    backend.send(
        to=recipients,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        attachments=attachments,
    )
