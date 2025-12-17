"""Adaptive tolerance helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Sequence, Tuple

from src.compiler.schema import AdaptiveThresholdCfg


def resolve_adaptive_tolerances(
    *,
    period_start: Optional[datetime],
    run_timestamp: datetime,
    base_abs: Optional[float],
    base_pct: Optional[float],
    rules: Optional[Sequence[AdaptiveThresholdCfg]],
) -> Tuple[Optional[float], Optional[float]]:
    """Pick the tolerance that applies for the given period bucket."""
    if period_start is None or not rules:
        return base_abs, base_pct

    delta = run_timestamp - period_start
    age = timedelta(seconds=max(delta.total_seconds(), 0))

    for rule in rules:
        if _rule_matches(rule, age):
            abs_tol = rule.tolerance_abs if rule.tolerance_abs is not None else base_abs
            pct_tol = rule.tolerance_pct if rule.tolerance_pct is not None else base_pct
            return abs_tol, pct_tol

    return base_abs, base_pct


def _rule_matches(rule: AdaptiveThresholdCfg, age: timedelta) -> bool:
    if rule.when == "last_hours":
        assert rule.hours is not None  # validated earlier
        return age <= timedelta(hours=rule.hours)
    if rule.when == "older_than_days":
        assert rule.days is not None
        return age >= timedelta(days=rule.days)
    return False
