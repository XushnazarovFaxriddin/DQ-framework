from datetime import datetime

from src.runtime.context import RunContext
from src.runtime.results import CheckResult, RunResult
from src.runtime.results_persistence import _map_check_row, _map_run_row
from src.utils.logger import RUN_ID


def _build_context() -> RunContext:
    return RunContext(
        env="cert",
        run_label="nightly",
        source_uri="src",
        target_uri="tgt",
        source=object(),
        target=object(),
        engines=("bigquery", "bigquery"),
    )


def test_map_run_row_populates_metadata():
    ctx = _build_context()
    run = RunResult(
        overall_status="FAIL",
        checks=[],
    )
    row = _map_run_row(run, ctx, datetime(2025, 1, 1), datetime(2025, 1, 1, 1), {"pass": 1, "fail": 2, "skip": 3})

    assert row["run_id"] == RUN_ID
    assert row["env"] == ctx.env
    assert row["run_label"] == ctx.run_label
    assert row["overall_status"] == "FAIL"
    assert row["pass_count"] == 1
    assert row["fail_count"] == 2
    assert row["skip_count"] == 3


def test_map_check_row_extracts_summary_and_reference():
    details = {
        "summary": {
            "severity_level": "CRITICAL",
            "mismatched_periods": 1,
            "periods_checked": 5,
            "rows_examined": 100,
        },
        "reference": {"stats_table": "dqf_monitoring.dqf_table_stats"},
        "mismatches": [{"period_key": "2025-01"}],
        "mismatch_csv_uri": "gs://bucket/mismatch.csv",
    }
    check = CheckResult(
        table="dqf_runs",
        check_type="stats_compare",
        status="FAIL",
        details=details,
    )

    row = _map_check_row(check)
    assert row["run_id"] == RUN_ID
    assert row["table_name"] == "dqf_runs"
    assert row["check_type"] == "stats_compare"
    assert row["status"] == "FAIL"
    assert row["mismatch_csv_uri"] == "gs://bucket/mismatch.csv"
    assert "extra_context" in row and "mismatched_periods" in (row["extra_context"] or "")
