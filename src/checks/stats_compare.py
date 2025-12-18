"""Compare stored table statistics (dqf_monitoring.dqf_table_stats)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dateutil import parser as dtparser
from dateutil.relativedelta import relativedelta

from src.checks.base import BaseCheck
from src.compiler.schema import (
    QueryCfg,
    StatsCompareWindowCfg,
    TableStatsMetricCfg,
)
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
from src.utils.adaptive_thresholds import resolve_adaptive_tolerances
from src.utils.logger import log
from src.utils.severity import (
    SeverityContext,
    determine_severity,
    highest_severity,
)


_EPS = 1e-12
_MAX_DETAILS = 10
_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
_SEVERITY_THRESHOLDS = [("HIGH", 180), ("MEDIUM", 60), ("LOW", 0)]


class _Window:
    def __init__(self, cfg: StatsCompareWindowCfg, now: datetime) -> None:
        self.granularity = cfg.period_granularity
        self.lookback_desc = self._describe(cfg)
        delta = timedelta(
            days=cfg.lookback_days or 0,
            weeks=cfg.lookback_weeks or 0,
        )
        rel = relativedelta(
            months=cfg.lookback_months or 0,
            years=cfg.lookback_years or 0,
        )
        self.start = now - delta - rel

    def _describe(self, cfg: StatsCompareWindowCfg) -> str:
        parts: List[str] = []
        if cfg.lookback_years:
            parts.append(f"{cfg.lookback_years}y")
        if cfg.lookback_months:
            parts.append(f"{cfg.lookback_months}mo")
        if cfg.lookback_weeks:
            parts.append(f"{cfg.lookback_weeks}w")
        if cfg.lookback_days:
            parts.append(f"{cfg.lookback_days}d")
        return " ".join(parts) or "latest"


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    if isinstance(value, str):
        try:
            return dtparser.parse(value)
        except Exception:
            return None
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float):
        return value
    if isinstance(value, (int, bool)):
        return float(value)
    try:
        return float(value)
    except Exception:
        return None


@register_check("stats_compare")
class StatsCompareCheck(BaseCheck):
    def run(self) -> CheckResult:
        stats_table = self._resolve_stats_table()
        metrics = self._resolve_metrics()
        run_timestamp = self._resolve_run_timestamp()
        windows = self._build_windows(run_timestamp)

        if not stats_table:
            return self._make_skip("missing_stats_table")
        if not metrics:
            return self._make_skip("no_metrics")
        if not windows:
            return self._make_skip("no_windows")

        table_name = self.check_cfg.table_name or self.table_cfg.name
        stats_connector = self._resolve_stats_connector()
        base_sql = stats_connector.render_select_sql(
            QueryCfg(table=stats_table)
        )

        metric_names = self._metric_names(metrics)
        metric_clause = self._metric_in_clause(metric_names)
        all_rows: List[Dict[str, Any]] = []

        for window in windows:
            query = self._build_window_query(
                base_sql=base_sql,
                table_name=table_name,
                window=window,
                metric_clause=metric_clause,
            )
            try:
                df = stats_connector.fetch_df(query)
            except Exception as exc:
                log(
                    "stats_compare.fetch.error",
                    level="ERROR",
                    table=table_name,
                    stats_table=stats_table,
                    error=str(exc),
                )
                return CheckResult(
                    table=self.table_cfg.name,
                    check_type="stats_compare",
                    status="FAIL",
                    details={"error": str(exc)},
                )
            if df.empty:
                continue
            all_rows.extend(df.to_dict("records"))

        if not all_rows:
            return self._make_skip("no_stats_rows")

        mismatches, periods_checked, overall_severity, oldest_mismatch, severity_level = self._evaluate_mismatches(
            all_rows, metric_names, run_timestamp, self.check_cfg.severity_rules
        )
        status = "PASS" if not mismatches else "FAIL"

        min_window = min((w.start for w in windows), default=None)
        details = {
            "stats_table": stats_table,
            "table_name": table_name,
            "metrics": [m.metric_name for m in metrics],
            "windows": [
                {
                    "period_granularity": w.granularity,
                    "start": w.start.isoformat(),
                    "lookback": w.lookback_desc,
                }
                for w in windows
            ],
            "rows_examined": len(all_rows),
            "mismatch_count": len(mismatches),
            "summary": {
                "periods_checked": periods_checked,
                "mismatched_periods": len(mismatches),
                "severity": overall_severity,
                "severity_level": severity_level,
                "oldest_mismatch": oldest_mismatch.isoformat()
                if oldest_mismatch
                else None,
            },
            "reference": {
                "stats_table": stats_table,
                "table_name": table_name,
                "lookback_cutoff": min_window.isoformat() if min_window else None,
                "granularities": sorted({w.granularity for w in windows}),
            },
        }
        if mismatches:
            details["mismatches"] = mismatches[:_MAX_DETAILS]

        return CheckResult(
            table=self.table_cfg.name,
            check_type="stats_compare",
            status=status,
            details=details,
            severity=severity_level if mismatches else None,
        )

    def _make_skip(self, reason: str) -> CheckResult:
        return CheckResult(
            table=self.table_cfg.name,
            check_type="stats_compare",
            status="SKIP",
            details={"reason": reason},
        )

    def _resolve_stats_table(self) -> Optional[str]:
        if self.check_cfg.stats_table:
            return self.check_cfg.stats_table
        return os.getenv("DQF_STATS_TABLE")

    def _resolve_stats_connector(self):
        side = (self.check_cfg.stats_table_side or "target").lower()
        return self.source if side == "source" else self.target

    def _resolve_run_timestamp(self) -> datetime:
        value = self.vars_map.get("run_timestamp")
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                parsed = dtparser.parse(value)
                if isinstance(parsed, datetime):
                    return parsed
            except Exception:
                pass
        return datetime.utcnow()

    def _resolve_metrics(self) -> List[TableStatsMetricCfg]:
        metrics = self.check_cfg.metrics or []
        return [m for m in metrics if m.method]

    def _build_windows(self, now: datetime) -> List[_Window]:
        raw = self.check_cfg.compare_on or []
        result: List[_Window] = []
        for cfg in raw:
            window = self._normalize_window(cfg, now)
            if window:
                result.append(window)
        return result

    def _normalize_window(
        self, cfg: StatsCompareWindowCfg, now: datetime
    ) -> Optional[_Window]:
        fields = (
            cfg.lookback_days,
            cfg.lookback_weeks,
            cfg.lookback_months,
            cfg.lookback_years,
        )
        if all(v in (None, 0) for v in fields):
            log(
                "stats_compare.window.skipped",
                table=self.table_cfg.name,
                granularity=cfg.period_granularity,
                reason="no_lookback",
            )
            return None
        return _Window(cfg, now)

    def _metric_in_clause(self, names: Sequence[str]) -> str:
        if not names:
            return ""
        encoded = ", ".join(f"'{self._escape_literal(n)}'" for n in names)
        return f"AND metric_name IN ({encoded})"

    def _metric_names(self, metrics: Sequence[TableStatsMetricCfg]) -> List[str]:
        return [
            m.name
            if m.name
            else f"{m.method}:{(m.column or '*').strip() or '*'}"
            for m in metrics
        ]

    def _build_window_query(
        self,
        base_sql: str,
        table_name: str,
        window: _Window,
        metric_clause: str,
    ) -> str:
        connector = self._resolve_stats_connector()
        engine = connector.engine_name

        # Format timestamp for different engines
        ts_expr = self._format_timestamp_expr(engine, window.start)

        return f"""
WITH stats AS ({base_sql})
SELECT
  period_key,
  period_granularity,
  period_start,
  period_end,
  side,
  metric_name,
  metric_value
FROM stats
WHERE table_name = '{self._escape_literal(table_name)}'
  AND period_granularity = '{self._escape_literal(window.granularity)}'
  AND period_start >= {ts_expr}
  {metric_clause}
ORDER BY period_start ASC
"""

    def _format_timestamp_expr(self, engine: str, dt: datetime) -> str:
        """Format timestamp expression for different database engines."""
        iso = dt.isoformat()
        if engine == "bigquery":
            return f"TIMESTAMP('{iso}')"
        if engine == "postgres":
            return f"TIMESTAMP '{iso}'"
        if engine == "oracle":
            return f"TO_TIMESTAMP('{iso}', 'YYYY-MM-DD\"T\"HH24:MI:SS')"
        if engine == "mssql":
            return f"CAST('{iso}' AS DATETIME2)"
        # Default fallback
        return f"TIMESTAMP('{iso}')"

    def _evaluate_mismatches(
        self,
        rows: List[Dict[str, Any]],
        metric_names: Sequence[str],
        run_timestamp: datetime,
        severity_rules: Optional[List["SeverityRuleCfg"]],
    ) -> Tuple[List[Dict[str, Any]], int, str, Optional[datetime], str]:
        buckets: Dict[
            Tuple[str, str, str], Dict[str, Any]
        ] = {}
        for row in rows:
            metric_name = str(row.get("metric_name") or "")
            granularity = str(row.get("period_granularity") or "")
            period_key = row.get("period_key") or self._format_period_key(
                row
            )
            key = (metric_name, granularity, period_key)
            bucket = buckets.setdefault(
                key,
                {
                    "metric_name": metric_name,
                    "period_granularity": granularity,
                    "period_key": period_key,
                    "period_start": _to_datetime(row.get("period_start")),
                    "period_end": _to_datetime(row.get("period_end")),
                    "values": {},
                },
            )
            side = str(row.get("side") or "").lower()
            if side in ("source", "target"):
                bucket["values"][side] = row.get("metric_value")

        mismatches: List[Dict[str, Any]] = []
        names_set = set(metric_names)
        severity = "LOW"
        oldest_mismatch: Optional[datetime] = None
        severity_level = "INFO"
        for bucket in buckets.values():
            if names_set and bucket["metric_name"] not in names_set:
                continue
            source = bucket["values"].get("source")
            target = bucket["values"].get("target")
            reason = self._missing_reason(source, target)
            abs_tol, pct_tol = resolve_adaptive_tolerances(
                period_start=bucket["period_start"],
                run_timestamp=run_timestamp,
                base_abs=self.check_cfg.tolerance_abs,
                base_pct=self.check_cfg.tolerance_pct,
                rules=self.check_cfg.adaptive_thresholds,
            )
            passes = self._passes_tolerance(source, target, abs_tol, pct_tol)
            if passes and reason is None:
                continue
            diff = self._diff_val(source, target)
            pct = self._pct_diff(source, target, diff)
            age_days = (
                (run_timestamp - bucket["period_start"]).days
                if bucket["period_start"]
                else 0
            )
            sev = self._severity_for_age(age_days)
            if _SEVERITY_ORDER[sev] > _SEVERITY_ORDER[severity]:
                severity = sev
            if bucket["period_start"]:
                if (
                    oldest_mismatch is None
                    or bucket["period_start"] < oldest_mismatch
                ):
                    oldest_mismatch = bucket["period_start"]
            mismatch_severity = determine_severity(
                context=SeverityContext(
                    diff=diff,
                    pct_diff=pct,
                    age_days=age_days,
                    reason=reason,
                ),
                rules=severity_rules,
                default="WARNING",
            )
            severity_level = highest_severity(severity_level, mismatch_severity)
            mismatches.append(
                {
                    "metric_name": bucket["metric_name"],
                    "period_granularity": bucket["period_granularity"],
                    "period_key": bucket["period_key"],
                    "period_start": bucket["period_start"].isoformat()
                    if bucket["period_start"]
                    else None,
                    "period_end": bucket["period_end"].isoformat()
                    if bucket["period_end"]
                    else None,
                    "source_value": source,
                    "target_value": target,
                    "diff": diff,
                    "pct_diff": pct,
                    "reason": reason or "threshold",
                    "severity": sev,
                    "severity_level": mismatch_severity,
                    "age_days": age_days,
                }
            )

        mismatches.sort(
            key=lambda entry: abs(entry["diff"]) if entry["diff"] is not None else float("inf"),
            reverse=True,
        )
        return mismatches, len(buckets), severity, oldest_mismatch, severity_level

    def _format_period_key(self, row: Dict[str, Any]) -> str:
        period_start = _to_datetime(row.get("period_start"))
        if period_start:
            return period_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        return str(row.get("period_key") or "unknown")

    def _severity_for_age(self, age_days: float) -> str:
        for label, threshold in _SEVERITY_THRESHOLDS:
            if age_days >= threshold:
                return label
        return "LOW"

    def _missing_reason(self, source: Any, target: Any) -> Optional[str]:
        if source is None:
            return "missing_source"
        if target is None:
            return "missing_target"
        return None

    def _passes_tolerance(
        self,
        source: Any,
        target: Any,
        abs_tol: Optional[float],
        pct_tol: Optional[float],
    ) -> bool:
        source_val = _safe_float(source)
        target_val = _safe_float(target)
        if source_val is None or target_val is None:
            return False
        diff = abs(source_val - target_val)
        effective_abs = abs_tol if abs_tol is not None else self.check_cfg.tolerance_abs
        effective_pct = pct_tol if pct_tol is not None else self.check_cfg.tolerance_pct
        if effective_abs is not None and diff <= effective_abs:
            return True
        if effective_pct is not None:
            base = max(abs(target_val), abs(source_val), _EPS)
            if (diff / base) * 100 <= effective_pct:
                return True
        return diff < _EPS

    def _diff_val(self, source: Any, target: Any) -> Optional[float]:
        source_val = _safe_float(source)
        target_val = _safe_float(target)
        if source_val is None or target_val is None:
            return None
        return source_val - target_val

    def _pct_diff(self, source: Any, target: Any, diff: Optional[float]) -> Optional[float]:
        if diff is None:
            return None
        source_val = _safe_float(source)
        target_val = _safe_float(target)
        if source_val is None or target_val is None:
            return None
        base = max(abs(target_val), abs(source_val), _EPS)
        return (abs(diff) / base) * 100

    def _escape_literal(self, value: str) -> str:
        return value.replace("'", "''")
