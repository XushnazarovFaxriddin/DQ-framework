"""Table statistics collection check."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from src.checks.base import BaseCheck
from src.compiler.schema import TableStatsMetricCfg, TableStatsStorageCfg
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
from src.stats.storage import build_stats_storage
from src.utils.logger import log


_VALID_GRANULARITIES = {"day", "week", "month", "year"}


@register_check("table_stats")
class TableStatsCheck(BaseCheck):
    def run(self) -> CheckResult:
        metrics = self.check_cfg.metrics or []
        storage_cfg = self._resolve_storage_cfg()
        granularity = (self.check_cfg.time_granularity or "month").lower()

        if not storage_cfg or not storage_cfg.table:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="table_stats",
                status="SKIP",
                details={"reason": "missing_stats_storage"},
            )
        if not metrics:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="table_stats",
                status="SKIP",
                details={"reason": "no_metrics_configured"},
            )
        if granularity not in _VALID_GRANULARITIES:
            raise ValueError(f"Unsupported time_granularity: {granularity}")

        rows: List[Dict[str, Any]] = []
        sides = self._resolve_sides(self.check_cfg.on)
        for side in sides:
            connector = self.source if side == "source" else self.target
            query_cfg = self.table_cfg.source if side == "source" else self.table_cfg.target
            base_sql = connector.render_select_sql(query_cfg)
            time_column = self._resolve_time_column(side)
            if not time_column:
                log(
                    "table_stats.missing_time_column",
                    table=self.table_cfg.name,
                    side=side,
                )
                continue

            for metric in metrics:
                try:
                    query = self._build_metric_query(
                        connector.engine_name,
                        base_sql,
                        time_column,
                        granularity,
                        metric,
                    )
                    df = connector.fetch_df(query)
                except Exception as exc:
                    log(
                        "table_stats.metric.error",
                        level="ERROR",
                        table=self.table_cfg.name,
                        side=side,
                        metric=metric.method,
                        error=str(exc),
                    )
                    continue
                rows.extend(
                    self._rows_from_df(
                        df,
                        side,
                        metric,
                        time_column,
                        granularity,
                    )
                )

        if not rows:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="table_stats",
                status="SKIP",
                details={"reason": "no_rows_collected"},
            )

        try:
            storage = build_stats_storage(storage_cfg)
            storage.persist(rows)
        except Exception as exc:
            log(
                "table_stats.storage.error",
                level="ERROR",
                table=self.table_cfg.name,
                error=str(exc),
            )
            return CheckResult(
                table=self.table_cfg.name,
                check_type="table_stats",
                status="FAIL",
                details={"error": str(exc)},
            )

        return CheckResult(
            table=self.table_cfg.name,
            check_type="table_stats",
            status="RECORDED",
            details={
                "stats_table": storage_cfg.table,
                "rows": len(rows),
                "run_timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

    def _resolve_sides(self, on_value: Optional[str]) -> Sequence[str]:
        if not on_value or on_value.lower() == "source":
            return ("source",)
        norm = on_value.lower()
        if norm == "target":
            return ("target",)
        if norm == "both":
            return ("source", "target")
        raise ValueError(f"Unknown side '{on_value}' for table_stats")

    def _resolve_time_column(self, side: str) -> Optional[str]:
        if side == "source":
            return self.check_cfg.time_column_source or self.check_cfg.time_column
        return self.check_cfg.time_column_target or self.check_cfg.time_column

    def _resolve_storage_cfg(self) -> Optional[TableStatsStorageCfg]:
        if self.check_cfg.stats_storage:
            return self.check_cfg.stats_storage
        table = os.getenv("DQF_STATS_TABLE")
        if not table:
            return None
        return TableStatsStorageCfg(table=table, project=os.getenv("DQF_STATS_PROJECT"))

    def _metric_sql(self, metric: TableStatsMetricCfg) -> str:
        method = metric.method.lower()
        column = (metric.column or "").strip()
        if method == "count":
            if column and column != "*":
                return f"COUNT({column})"
            return "COUNT(*)"
        if method == "distinct_count":
            if not column:
                raise ValueError("distinct_count requires a column")
            return f"COUNT(DISTINCT {column})"
        if method in {"sum", "avg", "min", "max"}:
            if not column:
                raise ValueError(f"{method} requires a column")
            return f"{method.upper()}({column})"
        raise ValueError(f"Unsupported stats metric method: {metric.method}")

    def _build_metric_query(
        self,
        engine_name: str,
        base_sql: str,
        time_column: str,
        granularity: str,
        metric: TableStatsMetricCfg,
    ) -> str:
        bucket_expr = self._bucket_start(engine_name, time_column, granularity)
        bucket_end = self._bucket_end(engine_name, bucket_expr, granularity)
        metric_expr = self._metric_sql(metric)
        return f"""
WITH base AS ({base_sql})
SELECT
  {bucket_expr} AS period_start,
  {bucket_end} AS period_end,
  {metric_expr} AS metric_value,
  COUNT(*) AS row_count
FROM base
GROUP BY {bucket_expr}
ORDER BY {bucket_expr}
"""

    def _bucket_start(self, engine_name: str, time_column: str, granularity: str) -> str:
        unit = granularity.upper()
        if engine_name == "bigquery":
            return f"TIMESTAMP_TRUNC(CAST({time_column} AS TIMESTAMP), {unit})"
        if engine_name == "postgres":
            return f"DATE_TRUNC('{granularity}', {time_column})"
        if engine_name == "oracle":
            oracle_unit = {
                "day": "DD",
                "week": "IW",
                "month": "MM",
                "year": "YYYY",
            }.get(granularity, "MM")
            return f"TRUNC({time_column}, '{oracle_unit}')"
        raise ValueError(f"Unsupported engine for table_stats: {engine_name}")

    def _bucket_end(self, engine_name: str, bucket_expr: str, granularity: str) -> str:
        if engine_name == "bigquery":
            return f"TIMESTAMP_ADD({bucket_expr}, INTERVAL 1 {granularity.upper()})"
        if engine_name == "postgres":
            return f"({bucket_expr} + INTERVAL '1 {granularity}')"
        if engine_name == "oracle":
            if granularity == "week":
                return f"({bucket_expr} + INTERVAL '7' DAY)"
            unit = {"day": "DAY", "month": "MONTH", "year": "YEAR"}.get(granularity, "MONTH")
            return f"({bucket_expr} + INTERVAL '1 {unit}')"
        raise ValueError(f"Unsupported engine for bucket end: {engine_name}")

    def _rows_from_df(
        self,
        df: pd.DataFrame,
        side: str,
        metric: TableStatsMetricCfg,
        time_column: str,
        granularity: str,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            period_start = self._to_datetime(row.get("period_start"))
            period_end = self._to_datetime(row.get("period_end"))
            if period_start is None:
                continue
            metric_value = row.get("metric_value")
            if pd.isna(metric_value):
                metric_value = None
            row_count = row.get("row_count")
            if pd.isna(row_count):
                row_count = None
            rows.append(
                {
                    "run_id": os.getenv("DQF_RUN_ID"),
                    "env": self.vars_map.get("env"),
                    "table_name": self.table_cfg.name,
                    "side": side,
                    "time_column": time_column,
                    "period_granularity": granularity,
                    "period_start": period_start,
                    "period_end": period_end,
                    "period_key": self._format_period_key(period_start, granularity),
                    "metric_name": metric.name or f"{metric.method}:{metric.column or '*'}",
                    "column_name": metric.column,
                    "metric_value": metric_value,
                    "row_count": int(row_count) if row_count is not None else None,
                    "computed_at": datetime.utcnow(),
                }
            )
        return rows

    def _format_period_key(self, value: datetime, granularity: str) -> str:
        if granularity == "day":
            return value.strftime("%Y-%m-%d")
        if granularity == "week":
            iso = value.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        if granularity == "month":
            return value.strftime("%Y-%m")
        if granularity == "year":
            return value.strftime("%Y")
        return value.isoformat()

    def _to_datetime(self, value: Optional[Any]) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
