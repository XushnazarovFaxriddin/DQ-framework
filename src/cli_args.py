"""Command line argument parsing for DQF."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class ParsedArgs:
    """Normalized view over CLI options returned by :func:`parse_args`."""

    config_file: str
    filetype: str
    vars: Dict[str, Any]
    alerts_override: Optional[List[Dict[str, Any]]]
    concurrency: int
    concurrency_checks: int
    table_timeout_sec: Optional[int]
    check_timeout_sec: Optional[int]
    max_rows_preview: int


def _flatten_cli_list(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    flattened: List[str] = []
    for raw in values:
        if raw is None:
            continue
        pieces = [part.strip() for part in raw.split(",")]
        flattened.extend([p for p in pieces if p])
    return flattened


def _parse_kv_list(pairs: Optional[Iterable[str]]) -> Dict[str, str]:
    """Parse key=value pairs coming from ``--vars`` or derived helpers."""

    out: Dict[str, str] = {}
    for kv in _flatten_cli_list(pairs):
        if "=" not in kv:
            raise ValueError(f"Invalid key=value item: {kv}")
        key, value = kv.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Empty key in item: {kv}")
        out[key] = value
    return out


def _parse_alert_tokens(
    tokens: Optional[Iterable[str]],
) -> Optional[List[Dict[str, Any]]]:
    """Parse ``--alerts`` override tokens into a list of alert route dictionaries."""

    items = _flatten_cli_list(tokens)
    if not items:
        return None

    routes: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def ensure_current(kind: str) -> Dict[str, Any]:
        nonlocal current
        if current is not None:
            routes.append(current)
        current = {"kind": kind}
        return current

    for token in items:
        if ":" in token:
            kind, remainder = token.split(":", 1)
            kind = kind.strip()
            if not kind:
                raise ValueError(f"Invalid alerts token: {token}")
            cur = ensure_current(kind)
            remainder = remainder.strip()
            if remainder:
                if "=" not in remainder:
                    raise ValueError(
                        f"Invalid alerts token (expected key=value after ':'): {token}"
                    )
                key, value = remainder.split("=", 1)
                cur[key.strip()] = value
            continue

        if "=" in token:
            if current is None:
                raise ValueError(
                    "Alert option without a preceding backend declaration. Use 'kind:key=value' syntax."
                )
            key, value = token.split("=", 1)
            current[key.strip()] = value
            continue

        # Token without ':' or '=' -> treat as bare backend identifier
        ensure_current(token)

    if current is not None:
        routes.append(current)

    return routes


def _typed_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def parse_args(argv: List[str]) -> ParsedArgs:
    """Parse CLI arguments, normalizing ``--vars`` and overrides."""

    parser = argparse.ArgumentParser(
        prog="dqf",
        description="DQF — Config-driven, pluggable Data Quality Framework",
    )

    parser.add_argument(
        "--config-file", required=True, help="Path to YAML or Python config file"
    )
    parser.add_argument(
        "--filetype", required=True, choices=["yaml", "py"], help="Config type"
    )

    parser.add_argument(
        "--vars",
        nargs="*",
        help="key=value pairs, supports comma or space separation (e.g. --vars env=prod run_label=nightly)",
    )
    parser.add_argument("--env", help="Environment name (e.g., prod)")
    parser.add_argument(
        "--run_label", help="Label for this run (e.g., nightly_2025-09-09)"
    )

    parser.add_argument(
        "--alerts",
        nargs="*",
        help="Override alerts routing. Example: gchat:webhook=... email:to=dq@corp.com",
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("DQF_CONCURRENCY", 4)),
        help="Max parallel tables",
    )
    parser.add_argument(
        "--concurrency_checks",
        type=int,
        default=int(os.getenv("DQF_CONCURRENCY_CHECKS", 1)),
        help="Max parallel checks per table",
    )
    parser.add_argument(
        "--table_timeout_sec",
        type=_typed_int,
        default=os.getenv("DQF_TABLE_TIMEOUT"),
        help="Optional timeout per table in seconds",
    )
    parser.add_argument(
        "--check_timeout_sec",
        type=_typed_int,
        default=os.getenv("DQF_CHECK_TIMEOUT"),
        help="Optional timeout per check in seconds",
    )
    parser.add_argument(
        "--max_rows_preview",
        type=int,
        default=int(os.getenv("DQF_MAX_ROWS_PREVIEW", 1000)),
        help="Max preview rows for diff attachments",
    )

    namespace = parser.parse_args(argv)

    vars_map = _parse_kv_list(namespace.vars)
    if namespace.env:
        vars_map.setdefault("env", namespace.env)
    if namespace.run_label:
        vars_map.setdefault("run_label", namespace.run_label)

    alerts_override = _parse_alert_tokens(namespace.alerts)

    table_timeout = (
        namespace.table_timeout_sec
        if isinstance(namespace.table_timeout_sec, int)
        else _typed_int(namespace.table_timeout_sec)
    )
    check_timeout = (
        namespace.check_timeout_sec
        if isinstance(namespace.check_timeout_sec, int)
        else _typed_int(namespace.check_timeout_sec)
    )

    return ParsedArgs(
        config_file=namespace.config_file,
        filetype=namespace.filetype,
        vars=vars_map,
        alerts_override=alerts_override,
        concurrency=namespace.concurrency,
        concurrency_checks=namespace.concurrency_checks,
        table_timeout_sec=table_timeout,
        check_timeout_sec=check_timeout,
        max_rows_preview=namespace.max_rows_preview,
    )
