from datetime import datetime, timedelta

from pytest import raises

from src.compiler.schema import AdaptiveThresholdCfg
from src.utils.adaptive_thresholds import resolve_adaptive_tolerances


def test_respects_last_hours_rule():
    now = datetime(2025, 1, 1, 12, 0, 0)
    rule = AdaptiveThresholdCfg(
        when="last_hours",
        hours=4,
        tolerance_pct=5.0,
    )
    abs_tol, pct_tol = resolve_adaptive_tolerances(
        period_start=now - timedelta(hours=2),
        run_timestamp=now,
        base_abs=0.0,
        base_pct=1.0,
        rules=[rule],
    )
    assert abs_tol == 0.0
    assert pct_tol == 5.0


def test_respects_older_than_days_rule():
    now = datetime(2025, 1, 1, 12, 0, 0)
    rule = AdaptiveThresholdCfg(
        when="older_than_days",
        days=7,
        tolerance_abs=10.0,
    )
    abs_tol, pct_tol = resolve_adaptive_tolerances(
        period_start=now - timedelta(days=10),
        run_timestamp=now,
        base_abs=1.0,
        base_pct=0.5,
        rules=[rule],
    )
    assert abs_tol == 10.0
    assert pct_tol == 0.5


def test_first_matching_rule_wins():
    now = datetime(2025, 1, 1, 12, 0, 0)
    rules = [
        AdaptiveThresholdCfg(
            when="last_hours",
            hours=6,
            tolerance_pct=7.0,
        ),
        AdaptiveThresholdCfg(
            when="last_hours",
            hours=24,
            tolerance_pct=1.0,
        ),
    ]
    abs_tol, pct_tol = resolve_adaptive_tolerances(
        period_start=now - timedelta(hours=2),
        run_timestamp=now,
        base_abs=None,
        base_pct=2.0,
        rules=rules,
    )
    assert pct_tol == 7.0
    assert abs_tol is None


def test_no_rules_returns_defaults():
    now = datetime.utcnow()
    abs_tol, pct_tol = resolve_adaptive_tolerances(
        period_start=now - timedelta(days=1),
        run_timestamp=now,
        base_abs=1.0,
        base_pct=0.25,
        rules=None,
    )
    assert abs_tol == 1.0
    assert pct_tol == 0.25


def test_invalid_rule_requires_fields():
    with raises(ValueError):
        AdaptiveThresholdCfg(when="last_hours", tolerance_pct=1.0)
