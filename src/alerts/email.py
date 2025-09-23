"""Email alert backend."""

from __future__ import annotations

import io
import os
import smtplib
from email.message import EmailMessage
from typing import Iterable, List, Tuple

import pandas as pd

from src.render.summarize import summarize_run
from src.render.tabular import markdown_summary_table
from src.runtime.registry import register_alert
from src.runtime.results import RunResult


def _iter_preview_payloads(
    result: RunResult, limit: int = 3
) -> Iterable[Tuple[str, pd.DataFrame]]:
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


def _attach_previews(
    msg: EmailMessage, previews: Iterable[Tuple[str, pd.DataFrame]]
) -> None:
    for name, df in previews:
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        payload = buffer.getvalue().encode("utf-8")
        msg.add_attachment(
            payload,
            maintype="text",
            subtype="csv",
            filename=f"{name}.csv",
        )


def _build_message(result: RunResult, recipients: List[str]) -> EmailMessage:
    msg = EmailMessage()
    subject = os.getenv("DQF_EMAIL_SUBJECT", "DQF Run Report")
    msg["Subject"] = f"{subject}: {result.overall_status}"
    msg["From"] = os.getenv("SMTP_FROM", "dqf@localhost")
    msg["To"] = ", ".join(recipients)

    summary_text = summarize_run(result)
    table_md = markdown_summary_table(result, max_rows=30)
    body = f"{summary_text}\n\n{table_md}\n"
    msg.set_content(body)
    msg.add_alternative(
        f"<pre>{summary_text}</pre><br/><pre>{table_md}</pre>", subtype="html"
    )

    _attach_previews(msg, _iter_preview_payloads(result))
    return msg


@register_alert("email")
def send_email(result: RunResult, *, recipients: List[str]) -> None:
    if not recipients:
        return

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "25"))
    if not host:
        raise EnvironmentError(
            "SMTP_HOST environment variable is required for email alerts"
        )

    msg = _build_message(result, recipients)

    with smtplib.SMTP(host, port) as client:
        if os.getenv("SMTP_STARTTLS", "false").lower() == "true":
            client.starttls()
        user = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASS")
        if user and password:
            client.login(user, password)
        client.send_message(msg)
