"""Normalization utilities for validated configuration models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.compiler.schema import (
    AlertsCfg,
    CheckCfg,
    ColumnMapEntry,
    ConfigModel,
    TableCfg,
)


def _coerce_scalar(value: Any) -> Any:
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if text.lower() in {"none", "null"}:
        return None
    try:
        if text.startswith("0") and text != "0" and not text.startswith("0."):
            # Preserve leading-zero strings (e.g., zip codes)
            raise ValueError
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return value


def _coerce_vars_map(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {k: _coerce_scalar(v) for k, v in raw.items()}


def _normalize_column_map(
    mapping: Optional[Dict[str, Any]],
) -> Optional[Dict[str, ColumnMapEntry]]:
    if mapping is None:
        return None
    normalized: Dict[str, ColumnMapEntry] = {}
    for key, entry in mapping.items():
        if isinstance(entry, ColumnMapEntry):
            normalized[key] = entry
        elif isinstance(entry, dict):
            normalized[key] = ColumnMapEntry.model_validate(entry)
        else:
            raise TypeError(f"Invalid column_map entry for '{key}': {type(entry)}")
    return normalized


def _normalize_check(check: CheckCfg) -> CheckCfg:
    include_map = _normalize_column_map(check.include_map)
    if check.include_source and check.include_target:
        if len(check.include_source) != len(check.include_target):
            raise ValueError(
                f"Check '{check.type}' defines mismatched include_source/include_target lengths"
            )
    return check.model_copy(update={"include_map": include_map})


def _normalize_table(table: TableCfg) -> TableCfg:
    column_map = _normalize_column_map(table.column_map)
    checks = [_normalize_check(chk) for chk in table.checks]
    return table.model_copy(update={"column_map": column_map, "checks": checks})


def normalize_config(
    model: ConfigModel,
    vars_map: Dict[str, Any],
    *,
    alerts_override: Optional[List[Dict[str, Any]]] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> Tuple[ConfigModel, Dict[str, Any]]:
    """Normalize a validated :class:`ConfigModel` and runtime variables."""

    cfg = model.model_copy(deep=True)
    cfg_tables = [_normalize_table(t) for t in cfg.tables]
    cfg = cfg.model_copy(update={"tables": cfg_tables})

    if alerts_override is not None:
        alerts = cfg.alerts or AlertsCfg()
        alerts = alerts.model_copy(update={"routes": alerts_override})
        cfg = cfg.model_copy(update={"alerts": alerts})

    runtime_vars = _coerce_vars_map(vars_map)
    if cli_overrides:
        for key, value in cli_overrides.items():
            if value is not None:
                runtime_vars[key] = value

    return cfg, runtime_vars
