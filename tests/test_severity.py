from src.compiler.schema import SeverityRuleCfg
from src.utils.severity import SeverityContext, determine_severity, highest_severity


def test_rule_order_first_match_wins():
    rules = [
        SeverityRuleCfg(severity="WARNING"),
        SeverityRuleCfg(
            severity="CRITICAL", tolerance_pct_exceeded_gte=2.0
        ),
    ]
    context = SeverityContext(diff=0.0, pct_diff=3.0, age_days=1.0, reason=None)
    assert determine_severity(context=context, rules=rules) == "WARNING"


def test_specific_rule_can_override():
    rules = [
        SeverityRuleCfg(
            severity="WARNING", tolerance_pct_exceeded_lt=2.0
        ),
        SeverityRuleCfg(
            severity="CRITICAL", tolerance_pct_exceeded_gte=2.0
        ),
    ]
    context = SeverityContext(diff=0.0, pct_diff=2.5, age_days=1.0, reason=None)
    assert determine_severity(context=context, rules=rules) == "CRITICAL"


def test_default_when_no_rules():
    context = SeverityContext(diff=1.0, pct_diff=0.5, age_days=0.1, reason="missing")
    assert determine_severity(context=context, rules=None) == "WARNING"


def test_highest_severity_aggregates_levels():
    assert highest_severity("INFO", "CRITICAL", "WARNING") == "CRITICAL"
    assert highest_severity() == "INFO"
