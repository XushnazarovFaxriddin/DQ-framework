import pandas as pd
import pytest

from src.checks.join_rowdiff import JoinRowDiffCheck
from src.checks.registry import register_all_checks
from src.compiler.normalizer import normalize_config
from src.compiler.planner import build_plan
from src.compiler.schema import ConfigModel
from src.connectors.csv_local import CsvLocalConnector
from src.runtime.results import CheckResult


class SpyCsvConnector(CsvLocalConnector):
    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        self.last_sql: str | None = None

    def fetch_df(self, sql: str) -> pd.DataFrame:  # type: ignore[override]
        self.last_sql = sql
        return super().fetch_df(sql)


def _build_config(csv_path: str) -> ConfigModel:
    cfg_dict = {
        "connections": {
            "source_env_var": "SRC_URI",
            "target_env_var": "TGT_URI",
        },
        "defaults": {"hashing": {"algorithm": "double_md5"}},
        "tables": [
            {
                "name": "demo",
                "source": {"table": csv_path},
                "target": {"table": csv_path},
                "join_keys": {"source": ["id"], "target": ["id"]},
                "checks": [
                    {"type": "row_count"},
                ],
            }
        ],
        "planning": {
            "partitions": {
                "mode": "range",
                "start": "2024-01-01T00:00:00Z",
                "end": "2024-01-01T12:00:00Z",
            }
        },
    }
    return ConfigModel.model_validate(cfg_dict)


@pytest.fixture
def sample_csv(tmp_path):
    df = pd.DataFrame(
        [
            {"id": 1, "name": "Alice", "score": 9.1},
            {"id": 2, "name": "Bob", "score": 8.4},
            {"id": 3, "name": "Charlie", "score": 7.2},
        ]
    )
    path = tmp_path / "data.csv"
    df.to_csv(path, index=False)
    return str(path)


def test_build_plan_respects_partition_range(sample_csv, monkeypatch):
    model = _build_config(sample_csv)
    cfg, runtime_vars = normalize_config(model, {"env": "test"}, cli_overrides={})
    plan = build_plan(cfg, runtime_vars)
    assert len(plan.tables) == 1
    partition = plan.tables[0].partition
    assert partition is not None
    assert partition.start.isoformat().startswith("2024-01-01T00:00:00")
    assert partition.end.isoformat().startswith("2024-01-01T12:00:00")


def test_plan_run_with_csv_connectors(sample_csv, monkeypatch):
    register_all_checks()
    model = _build_config(sample_csv)
    cfg, runtime_vars = normalize_config(
        model,
        {"env": "unit", "run_label": "test"},
        cli_overrides={"concurrency": 1, "concurrency_checks": 1},
    )
    monkeypatch.setenv("SRC_URI", "csv://")
    monkeypatch.setenv("TGT_URI", "csv://")

    plan = build_plan(cfg, runtime_vars)
    run_result = plan.run()
    assert run_result.overall_status == "PASS"
    assert any(isinstance(check, CheckResult) for check in run_result.checks)


def test_join_rowdiff_applies_ordering(sample_csv):
    cfg_dict = {
        "connections": {
            "source_env_var": "SRC_URI",
            "target_env_var": "TGT_URI",
        },
        "defaults": {"hashing": {"algorithm": "double_md5"}},
        "tables": [
            {
                "name": "demo",
                "source": {"table": sample_csv},
                "target": {"table": sample_csv},
                "join_keys": {"source": ["id"], "target": ["id"]},
                "checks": [
                    {
                        "type": "join_rowdiff",
                        "include": ["name", "score"],
                        "order_by": ["name"],
                    }
                ],
            }
        ],
    }
    model = ConfigModel.model_validate(cfg_dict)
    table_cfg = model.tables[0]
    check_cfg = table_cfg.checks[0]

    source = SpyCsvConnector("csv://")
    target = SpyCsvConnector("csv://")

    check = JoinRowDiffCheck(
        table_cfg=table_cfg,
        check_cfg=check_cfg,
        source=source,
        target=target,
        vars_map={"max_rows_preview": 10},
    )

    result = check.run()
    assert result.status == "PASS"
    assert source.last_sql is not None and "ORDER BY" in source.last_sql
    assert target.last_sql is not None and "ORDER BY" in target.last_sql
