"""BigQuery storage for DQF runs and check results."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from src.utils.logger import log

if TYPE_CHECKING:
    from src.compiler.schema import ResultsTableCfg
    from src.runtime.results import CheckResult, RunResult


def _env_str(var_name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(var_name)
    if val is None or val == "":
        return default
    return val


class ResultsStorageBackend(ABC):
    """Abstract base class for results storage backends."""

    @abstractmethod
    def persist_run(self, run_data: Dict[str, Any]) -> None:
        """Persist a single run record."""
        ...

    @abstractmethod
    def persist_checks(self, check_rows: List[Dict[str, Any]]) -> None:
        """Persist multiple check results."""
        ...


class BigQueryResultsStorage(ResultsStorageBackend):
    """BigQuery backend for storing DQF run and check results."""

    def __init__(
        self,
        runs_table: Optional[str] = None,
        checks_table: Optional[str] = None,
        project: Optional[str] = None,
    ) -> None:
        from google.cloud import bigquery

        self._runs_table = runs_table or _env_str("DQF_RUNS_TABLE")
        self._checks_table = checks_table or _env_str("DQF_CHECKS_TABLE")
        self._client = bigquery.Client(project=project)

    def persist_run(self, run_data: Dict[str, Any]) -> None:
        """Persist a single run record to BigQuery."""
        if not self._runs_table:
            log("results_storage.runs.skipped", reason="no_runs_table_configured")
            return

        from google.cloud import bigquery

        try:
            table_ref = bigquery.TableReference.from_string(
                self._runs_table, default_project=self._client.project
            )
            errors = self._client.insert_rows_json(table_ref, [run_data])
            if errors:
                log(
                    "results_storage.runs.error",
                    level="ERROR",
                    table=self._runs_table,
                    errors=str(errors),
                )
            else:
                log(
                    "results_storage.runs.ok",
                    table=self._runs_table,
                    run_id=run_data.get("run_id"),
                )
        except Exception as exc:
            log(
                "results_storage.runs.error",
                level="ERROR",
                table=self._runs_table,
                error=str(exc),
            )

    def persist_checks(self, check_rows: List[Dict[str, Any]]) -> None:
        """Persist multiple check results to BigQuery."""
        if not self._checks_table:
            log("results_storage.checks.skipped", reason="no_checks_table_configured")
            return

        if not check_rows:
            return

        from google.cloud import bigquery

        try:
            table_ref = bigquery.TableReference.from_string(
                self._checks_table, default_project=self._client.project
            )
            errors = self._client.insert_rows_json(table_ref, check_rows)
            if errors:
                log(
                    "results_storage.checks.error",
                    level="ERROR",
                    table=self._checks_table,
                    errors=str(errors),
                )
            else:
                log(
                    "results_storage.checks.ok",
                    table=self._checks_table,
                    rows=len(check_rows),
                )
        except Exception as exc:
            log(
                "results_storage.checks.error",
                level="ERROR",
                table=self._checks_table,
                error=str(exc),
            )


def build_results_storage(
    runs_cfg: Optional["ResultsTableCfg"] = None,
    checks_cfg: Optional["ResultsTableCfg"] = None,
) -> Optional[ResultsStorageBackend]:
    """Build a results storage backend from configuration."""
    runs_table = runs_cfg.table if runs_cfg and runs_cfg.enabled else _env_str("DQF_RUNS_TABLE")
    checks_table = checks_cfg.table if checks_cfg and checks_cfg.enabled else _env_str("DQF_CHECKS_TABLE")

    if not runs_table and not checks_table:
        return None

    project = None
    if runs_cfg and runs_cfg.project:
        project = runs_cfg.project
    elif checks_cfg and checks_cfg.project:
        project = checks_cfg.project

    return BigQueryResultsStorage(
        runs_table=runs_table,
        checks_table=checks_table,
        project=project,
    )


def format_run_row(
    run_result: "RunResult",
    config_file: str = "",
    env: str = "",
    run_label: str = "",
) -> Dict[str, Any]:
    """Format a RunResult into a BigQuery row for dqf_runs table."""
    now = datetime.now(timezone.utc)

    return {
        "run_id": run_result.run_id,
        "config_file": config_file,
        "env": env,
        "run_label": run_label,
        "status": run_result.status,
        "started_at": run_result.started_at.isoformat() if run_result.started_at else now.isoformat(),
        "completed_at": run_result.completed_at.isoformat() if run_result.completed_at else now.isoformat(),
        "duration_ms": run_result.duration_ms,
        "total_checks": run_result.total_checks,
        "passed_checks": run_result.passed_checks,
        "failed_checks": run_result.failed_checks,
        "skipped_checks": run_result.skipped_checks,
        "tables_processed": len(run_result.tables) if run_result.tables else 0,
        "has_critical_issues": any(
            check.details.get("has_extra_in_target", False)
            for check in run_result.checks
        ) if run_result.checks else False,
        "created_at": now.isoformat(),
    }


def format_check_row(
    check_result: "CheckResult",
    run_id: str,
    config_file: str = "",
    env: str = "",
) -> Dict[str, Any]:
    """Format a CheckResult into a BigQuery row for dqf_check_results table."""
    import json
    now = datetime.now(timezone.utc)

    # Extract key metrics from details
    details = check_result.details or {}
    source_count = details.get("source_count") or details.get("source")
    target_count = details.get("target_count") or details.get("target")

    # Handle aggregations rules
    if "rules" in details:
        rules = details["rules"]
        if rules and len(rules) > 0:
            first_rule = rules[0]
            if source_count is None:
                source_count = first_rule.get("source")
            if target_count is None:
                target_count = first_rule.get("target")

    return {
        "run_id": run_id,
        "config_file": config_file,
        "env": env,
        "table_name": check_result.table,
        "check_type": check_result.check_type,
        "status": check_result.status,
        "severity": check_result.severity,
        "source_value": source_count,
        "target_value": target_count,
        "has_extra_in_target": details.get("has_extra_in_target", False),
        "extra_in_target_count": details.get("extra_in_target_count", 0),
        "mismatch_ids_csv_uri": details.get("mismatch_ids_csv_uri"),
        "details_json": json.dumps(details) if details else None,
        "created_at": now.isoformat(),
    }


def persist_run_results(
    run_result: "RunResult",
    config_file: str = "",
    env: str = "",
    run_label: str = "",
    runs_cfg: Optional["ResultsTableCfg"] = None,
    checks_cfg: Optional["ResultsTableCfg"] = None,
) -> None:
    """
    Persist run and check results to BigQuery.

    This function persists:
    1. A single row to dqf_runs table with run summary
    2. Multiple rows to dqf_check_results table, one per check

    Tables can be configured via:
    - YAML config: results_storage.runs.table, results_storage.checks.table
    - Environment: DQF_RUNS_TABLE, DQF_CHECKS_TABLE
    """
    storage = build_results_storage(runs_cfg, checks_cfg)
    if not storage:
        return

    # Persist run summary
    run_row = format_run_row(
        run_result,
        config_file=config_file,
        env=env,
        run_label=run_label,
    )
    storage.persist_run(run_row)

    # Persist individual check results
    check_rows = [
        format_check_row(
            check,
            run_id=run_result.run_id,
            config_file=config_file,
            env=env,
        )
        for check in run_result.checks
    ]
    storage.persist_checks(check_rows)
