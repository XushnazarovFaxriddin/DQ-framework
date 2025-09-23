"""Alert dispatcher orchestrating registered backends."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from src.compiler.schema import ConfigModel
from src.runtime.registry import ALERTS
from src.runtime.results import RunResult
from src.utils.logger import log


def _resolve_email_recipients(route: Dict[str, Any]) -> List[str]:
    to = route.get("to")
    if isinstance(to, str):
        return [addr.strip() for addr in to.split(",") if addr.strip()]
    if isinstance(to, Iterable):
        recipients = [str(item).strip() for item in to if str(item).strip()]
        if recipients:
            return recipients
    env_list = os.getenv("DQ_EMAILS", "")
    return [addr.strip() for addr in env_list.split(",") if addr.strip()]


def dispatch_alerts(cfg: ConfigModel, run: RunResult) -> None:
    routes = (cfg.alerts.routes if cfg.alerts else []) or []
    if not routes:
        log("alerts.skip", reason="no_routes_configured")
        return

    for route in routes:
        kind = str(route.get("kind", "")).lower()
        if not kind:
            log("alerts.skip", reason="missing_kind", route=route)
            continue
        if kind not in ALERTS:
            log("alerts.unknown_backend", level="ERROR", backend=kind)
            continue

        try:
            if kind == "gchat":
                mode = route.get("mode", "text")
                ALERTS[kind](run, route=route, mode=mode)
                log("alerts.sent", backend="gchat", mode=mode)
            elif kind == "email":
                recipients = _resolve_email_recipients(route)
                if not recipients:
                    log("alerts.skip", backend="email", reason="no_recipients")
                    continue
                ALERTS[kind](run, recipients=recipients)
                log("alerts.sent", backend="email", recipients=len(recipients))
            else:
                ALERTS[kind](run, route=route)
                log("alerts.sent", backend=kind)
        except Exception as exc:
            log("alerts.error", level="ERROR", backend=kind, error=str(exc))
