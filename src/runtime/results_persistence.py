"""Persistence helpers for run/check result tables."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence

try:
    from google.cloud import bigquery
except ImportError:
    bigquery = None  # type: ignore

from src.compiler.schema import ResultsStorageCfg, ResultsTableCfg
from src.render.mismatch_links import csv_links_for_check
from src.runtime.context import RunContext
from src.runtime.results import CheckResult, RunResult
from src.utils.logger import RUN_ID, log



class _TableBackend(ABC):
    def __init__(self, table: str) -> None:
        self._table = table

    @property
    def table(self) -> str:
        return self._table

    @abstractmethod
    def persist(self, rows: Sequence[Mapping[str, Any]]) -> None:
        ...


class _BigQueryResultsBackend(_TableBackend):
    def __init__(self, table: str, project: Optional[str] = None) -> None:
        if bigquery is None:
            raise RuntimeError(
                "BigQuery results persistence requires 'google-cloud-bigquery'"
            )
        super().__init__(table)
        self._client = bigquery.Client(project=project)
        self._table_ref = bigquery.TableReference.from_string(table, default_project=project)

    def persist(self, rows: Sequence[Mapping[str, Any]]) -> None:
        if not rows:
            return
        errors = self._client.insert_rows_json(self._table_ref, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")


def _build_backend(cfg: ResultsTableCfg) -> Optional[_TableBackend]:
    if not cfg or not cfg.enabled or not cfg.table:
        return None
    if cfg.backend == "bigquery":
        try:
            return _BigQueryResultsBackend(table=cfg.table, project=cfg.project)
        except Exception as exc:
            log(
                "results.persistence.backend.error",
                level="WARNING",
                backend="bigquery",
                table=cfg.table,
                error=str(exc),
            )
            return None
    raise ValueError(f"Unsupported results backend: {cfg.backend}")


def _serialize_small(value: Any, limit: int = 1024) -> Optional[str]:
    if value is None:
        return None
    try:
        payload = json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        payload = str(value)
    if len(payload) > limit:
        return payload[:limit]
    return payload


def _format_ts(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _map_run_row(
    run: RunResult,
    context: RunContext,
    run_start: datetime,
    run_end: datetime,
    stats: Dict[str, int],
) -> Dict[str, Any]:
    table_count = len({check.table for check in run.checks}) if run.checks else None
    return {
        "run_id": RUN_ID,
        "env": context.env,
        "run_label": context.run_label,
        "started_at": _format_ts(run_start),
        "finished_at": _format_ts(run_end),
        "overall_status": run.overall_status,
        "pass_count": stats.get("pass"),
        "fail_count": stats.get("fail"),
        "skip_count": stats.get("skip"),
        "table_count": table_count,
        "extra_context": None,
    }


def _extract_period_key(details: Mapping[str, Any]) -> Optional[str]:
    mismatches = details.get("mismatches")
    if isinstance(mismatches, Sequence) and mismatches:
        first = mismatches[0]
        if isinstance(first, Mapping):
            period = first.get("period_key")
            if period:
                return period
    return None


def _map_check_row(check: CheckResult) -> Dict[str, Any]:
    details = check.details or {}
    csv_links = csv_links_for_check(check)
    extra_context = _serialize_small(details)
    # Map to BigQuery schema (scripts/bq_tables.sql -> dqf_check_results)
    return {
        "run_id": RUN_ID,
        "table_name": check.table,
        "check_type": check.check_type,
        "status": check.status,
        "severity": check.severity,
        "method": check.check_type,
        "metric_name": check.check_type,
        "column_name": None,
        "group_key": None,
        "period_granularity": None,
        "period_start": None,
        "period_end": None,
        "period_key": _extract_period_key(details if isinstance(details, Mapping) else {}),
        "source_value": None,
        "target_value": None,
        "diff_abs": None,
        "diff_pct": None,
        "mismatch_csv_uri": csv_links[0] if csv_links else None,
        "stats_table_ref": details.get("stats_table") if isinstance(details, Mapping) else None,
        "extra_context": extra_context,
    }


def persist_run_results(
    cfg: Optional[ResultsStorageCfg],
    *,
    context: RunContext,
    run: RunResult,
    checks: Sequence[CheckResult],
    run_start: datetime,
    run_end: datetime,
    stats: Dict[str, int],
) -> None:
    """Persist run/check rows when configured."""
    if not cfg:
        return
    run_backend = _build_backend(cfg.runs) if cfg.runs else None
    check_backend = _build_backend(cfg.checks) if cfg.checks else None
    run_row = _map_run_row(run, context, run_start, run_end, stats)
    check_rows = [_map_check_row(check) for check in checks]
    if run_backend:
        run_backend.persist([run_row])
        log(
            "results.persistence.runs.ok",
            table=run_backend.table,
            rows=1,
        )
    if check_backend and check_rows:
        check_backend.persist(check_rows)
        log(
            "results.persistence.checks.ok",
            table=check_backend.table,
            rows=len(check_rows),
        )
 
