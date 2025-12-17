import pytest

from src.alerts.dispatcher import dispatch_alerts
from src.compiler.schema import ConfigModel
from src.runtime.registry import ALERTS
from src.runtime.results import CheckResult, RunResult


@pytest.fixture(autouse=True)
def restore_alert_registry():
    original = dict(ALERTS)
    yield
    ALERTS.clear()
    ALERTS.update(original)


def test_email_alert_uses_env_recipients(monkeypatch):
    cfg_dict = {
        "connections": {"source_env_var": "SRC", "target_env_var": "TGT"},
        "tables": [],
        "alerts": {"routes": [{"kind": "email"}]},
    }
    cfg = ConfigModel.model_validate(cfg_dict)
    run = RunResult(
        overall_status="FAIL",
        checks=[CheckResult(table="t", check_type="row_count", status="FAIL")],
    )

    calls = []

    def fake_email_sender(result, *, recipients):
        calls.append(recipients)

    ALERTS["email"] = fake_email_sender

    monkeypatch.setenv("DQ_EMAILS", "jamshid.allayev@virginvoyages.com")

    dispatch_alerts(cfg, run)
    assert calls == [["a@example.com", "b@example.com"]]


def test_gchat_alert_uses_override(monkeypatch):
    cfg_dict = {
        "connections": {"source_env_var": "SRC", "target_env_var": "TGT"},
        "tables": [],
        "alerts": {"routes": [{"kind": "gchat", "webhook": "https://hook"}]},
    }
    cfg = ConfigModel.model_validate(cfg_dict)
    run = RunResult(overall_status="PASS", checks=[])

    calls = []

    def fake_gchat(result, *, route=None, mode="text"):
        calls.append((route, mode))

    ALERTS["gchat"] = fake_gchat

    dispatch_alerts(cfg, run)
    assert calls == [({"kind": "gchat", "webhook": "https://hook"}, "text")]
