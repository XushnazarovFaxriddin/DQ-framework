"""
Alert dispatcher:
- Supports route.mode for gchat: "card" or "text" (default: text)
- Email recipients from route.to or env DQ_EMAILS
"""

from typing import Any, Dict, List
import os

from src.runtime.registry import ALERTS
from src.utils.logger import log
from src.compiler.schema import ConfigModel
from src.runtime.results import RunResult


def _resolve_recipients(route: Dict[str, Any]) -> List[str]:
    to = route.get("to")
    if to and isinstance(to, list) and to:
        return [str(x).strip() for x in to if str(x).strip()]
    env_list = os.getenv("DQ_EMAILS")
    if not env_list:
        return []
    return [x.strip() for x in env_list.split(",") if x.strip()]


def dispatch_alerts(cfg: ConfigModel, run: RunResult) -> None:
    routes = (cfg.alerts.routes if cfg.alerts else []) or []
    if not routes:
        log("alerts.skip", reason="no_routes_configured")
        return

    for route in routes:
        kind = route.get("kind")
        if kind not in ALERTS:
            log("alerts.unknown_backend", level="ERROR", backend=kind)
            continue

        try:
            if kind == "gchat":
                mode = route.get("mode", "text")
                ALERTS[kind](run, route=route, mode=mode)
                log("alerts.sent", backend="gchat", mode=mode)

            elif kind == "email":
                recipients = _resolve_recipients(route)
                if not recipients:
                    log("alerts.skip", backend="email", reason="no_recipients")
                    continue
                ALERTS[kind](run, recipients=recipients)
                log("alerts.sent", backend="email", recipients=len(recipients))

            else:
                ALERTS[kind](run, route=route)  # generic
                log("alerts.sent", backend=kind)

        except Exception as e:
            log("alerts.error", level="ERROR", backend=kind, error=str(e))
