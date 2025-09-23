"""
Centralized registration for all built-in checks.

This module imports each check module to trigger @register_check decorators.
It also supports:
- DQF_DISABLE_CHECKS: comma-separated list of check names to skip after import
- DQF_EXTRA_CHECKS: comma-separated list of Python module paths to import (3rd-party checks)

Usage:
    from src.checks.registry import register_all_checks
    register_all_checks()  # typically called in main.py before planning/execution
"""

import importlib
import os
from typing import Dict

from src.runtime.registry import CHECKS, register_check
from src.utils.logger import log


def _safe_import(module_path: str) -> None:
    try:
        importlib.import_module(module_path)
        log("checks.registry.import.ok", module=module_path)
    except Exception as e:
        log("checks.registry.import.error", level="ERROR", module=module_path, error=str(e))


def _apply_disable_list() -> None:
    disable = os.getenv("DQF_DISABLE_CHECKS", "").strip()
    if not disable:
        return
    names = {x.strip() for x in disable.split(",") if x.strip()}
    if not names:
        return
    for n in list(CHECKS.keys()):
        if n in names:
            del CHECKS[n]
            log("checks.registry.disabled", name=n)


def _import_builtin_checks() -> None:
    """
    Import all first-party checks so their decorators execute.
    Keep explicit imports for clarity and predictable load order.
    """
    modules = [
        "src.checks.row_count",
        "src.checks.hash_diff",
        "src.checks.join_rowdiff",
        "src.checks.aggregations",
        "src.checks.freshness",
        "src.checks.partitions",
        "src.checks.schema_drift",
        # Optional adapters (safe import)
        "src.checks.expectations.ge_adapter",
        "src.checks.expectations.soda_adapter",
    ]
    for m in modules:
        _safe_import(m)

    # Ensure custom_check is available even if base wasn't imported elsewhere
    try:
        from src.checks.base import CustomCheck  # type: ignore
        register_check("custom_check")(CustomCheck)
        log("checks.registry.custom_check.enabled")
    except Exception as e:
        log("checks.registry.custom_check.error", level="ERROR", error=str(e))


def _import_extra_checks_from_env() -> None:
    extra = os.getenv("DQF_EXTRA_CHECKS", "").strip()
    if not extra:
        return
    modules = [x.strip() for x in extra.split(",") if x.strip()]
    for m in modules:
        _safe_import(m)


def register_all_checks() -> Dict[str, str]:
    """
    Import built-in checks, optional extras, apply disable list,
    and return a mapping of registered checks for diagnostics.
    """
    log("checks.registry.start")
    _import_builtin_checks()
    _import_extra_checks_from_env()
    _apply_disable_list()
    summary = {k: f"{v.__module__}.{v.__qualname__}" for k, v in CHECKS.items()}
    log("checks.registry.done", registered=len(summary))
    return summary
