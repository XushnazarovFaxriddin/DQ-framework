"""
Simple SMTP email sender.
Relies on env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_STARTTLS
"""

import os
import smtplib
from email.message import EmailMessage
from typing import List

from src.runtime.results import RunResult
from src.runtime.registry import register_alert


@register_alert("email")
def send_email(result: RunResult, *, recipients: List[str]) -> None:
    if not recipients:
        return

    msg = EmailMessage()
    msg["Subject"] = f"DQF: {result.overall_status}"
    msg["From"] = os.getenv("SMTP_FROM", "jamshid.allayev@virginvoyages.com")
    msg["To"] = ", ".join(recipients)

    lines = []
    for c in result.checks[:100]:
        lines.append(f"{c.table}:{c.check_type} -> {c.status} :: {c.details}")
    msg.set_content("\n".join(lines) or f"Status: {result.overall_status}")

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "25"))
    with smtplib.SMTP(host, port) as s:
        if os.getenv("SMTP_STARTTLS", "false").lower() == "true":
            s.starttls()
        user = os.getenv("SMTP_USER"); pwd = os.getenv("SMTP_PASS")
        if user and pwd:
            s.login(user, pwd)
        s.send_message(msg)
