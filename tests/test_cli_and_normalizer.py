import pytest

from src.cli_args import parse_args
from src.compiler.normalizer import normalize_config
from src.compiler.schema import ConfigModel


@pytest.fixture
def base_config_dict(tmp_path):
    cfg = {
        "connections": {
            "source_env_var": "SRC_URI",
            "target_env_var": "TGT_URI",
        },
        "defaults": {
            "hashing": {
                "algorithm": "double_md5",
                "delimiter": "|",
                "null_token": "__NULL__",
                "case": "lower",
            }
        },
        "tables": [
            {
                "name": "demo",
                "source": {"table": "demo_table"},
                "target": {"table": "demo_table"},
                "join_keys": {"source": ["id"], "target": ["id"]},
                "checks": [
                    {
                        "type": "row_count",
                        "order_by": ["id"],
                    }
                ],
            }
        ],
        "planning": {
            "partitions": {
                "mode": "range",
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-01-02T00:00:00Z",
            }
        },
    }
    return cfg


def test_cli_parse_and_alert_overrides():
    args = parse_args(
        [
            "--config-file",
            "cfg.yaml",
            "--filetype",
            "yaml",
            "--vars",
            "env=prod,run_label=nightly",
            "--alerts",
            "gchat:webhook=https://hook,mode=card",
            "email:to=dq@example.com",
            "--concurrency",
            "8",
            "--concurrency_checks",
            "2",
            "--table_timeout_sec",
            "30",
            "--check_timeout_sec",
            "15",
            "--max_rows_preview",
            "250",
        ]
    )

    assert args.vars["env"] == "prod"
    assert args.vars["run_label"] == "nightly"
    assert args.concurrency == 8
    assert args.table_timeout_sec == 30
    assert args.max_rows_preview == 250
    assert args.alerts_override == [
        {"kind": "gchat", "webhook": "https://hook", "mode": "card"},
        {"kind": "email", "to": "dq@example.com"},
    ]


def test_normalize_config_types_and_alert_override(base_config_dict):
    model = ConfigModel.model_validate(base_config_dict)
    raw_vars = {
        "env": "prod",
        "concurrency": "6",
        "feature_flag": "true",
        "threshold": "3.5",
    }

    cfg, runtime_vars = normalize_config(
        model,
        raw_vars,
        alerts_override=[{"kind": "gchat"}],
        cli_overrides={"concurrency_checks": 3, "max_rows_preview": 100},
    )

    assert cfg.alerts.routes == [{"kind": "gchat"}]
    assert runtime_vars["env"] == "prod"
    assert runtime_vars["concurrency"] == 6
    assert runtime_vars["concurrency_checks"] == 3
    assert runtime_vars["feature_flag"] is True
    assert pytest.approx(runtime_vars["threshold"]) == 3.5
