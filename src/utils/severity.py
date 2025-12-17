from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Sequence
from src.compiler.schema import SeverityRuleCfg

"""Severity helpers for check results and alerts."""




SEVERITY_LEVELS = ["INFO", "WARNING", "CRITICAL"]
_SEVERITY_ORDER = {value: idx for idx, value in enumerate(SEVERITY_LEVELS)}


@dataclass
class SeverityContext:
    diff: Optional[float]
    pct_diff: Optional[float]
    age_days: Optional[float]
    reason: Optional[str]


def normalize_severity(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).strip().upper()
    return normalized if normalized in _SEVERITY_ORDER else None


def severity_rank(value: Optional[str]) -> int:
    normalized = normalize_severity(value)
    if normalized is None:
        return 0
    return _SEVERITY_ORDER[normalized]


def highest_severity(*values: Optional[str]) -> str:
    best = "INFO"
    best_rank = severity_rank(best)
    for value in values:
        rank = severity_rank(value)
        if rank > best_rank:
            best = normalize_severity(value) or best
            best_rank = rank
    return best


def determine_severity(
    *,
    context: SeverityContext,
    rules: Optional[Sequence[SeverityRuleCfg]],
    default: str = "WARNING",
) -> str:
    """Pick the first severity rule that matches the provided context."""
    normalized_default = normalize_severity(default) or "WARNING"
    if not rules:
        return normalized_default

    for rule in rules:
        if _rule_matches(rule, context):
            return rule.severity
    return normalized_default


def _rule_matches(rule: SeverityRuleCfg, context: SeverityContext) -> bool:
    if rule.older_than_days is not None:
        if context.age_days is None or context.age_days < rule.older_than_days:
            return False
    if rule.newer_than_days is not None:
        if context.age_days is None or context.age_days > rule.newer_than_days:
            return False
    if rule.tolerance_pct_exceeded_gte is not None:
        if context.pct_diff is None or context.pct_diff < rule.tolerance_pct_exceeded_gte:
            return False
    if rule.tolerance_pct_exceeded_lt is not None:
        if context.pct_diff is None or context.pct_diff >= rule.tolerance_pct_exceeded_lt:
            return False
    if rule.tolerance_abs_exceeded_gte is not None:
        if context.diff is None or abs(context.diff) < rule.tolerance_abs_exceeded_gte:
            return False
    if rule.tolerance_abs_exceeded_lt is not None:
        if context.diff is None or abs(context.diff) >= rule.tolerance_abs_exceeded_lt:
            return False
    if rule.reason is not None and context.reason != rule.reason:
        return False
    return True
