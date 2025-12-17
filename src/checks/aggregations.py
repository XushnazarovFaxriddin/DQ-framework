"""Aggregations check with support for source_column and target_column."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dateutil import parser as dtparser

from src.checks.base import BaseCheck
from src.compiler.schema import CheckCfg, ColumnMapEntry, MismatchSamplingCfg
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
from src.utils.io import attach_csv_uri
from src.utils.logger import log
from src.utils.mismatch_sampling import MismatchSamplingResult, sample_mismatch_ranges
from src.utils.sql import wrap_order_by


def _map_order_by(
    columns: Optional[List[str]],
    column_map: Optional[Dict[str, ColumnMapEntry]],
    *,
    side: str,
) -> Optional[List[str]]:
    if not columns:
        return None
    if not column_map:
        return columns
    mapped: List[str] = []
    for canonical in columns:
        entry = column_map.get(canonical)
        if entry is None:
            mapped.append(canonical)
            continue
        mapped.append(entry.source if side == "source" else entry.target)
    return mapped


@register_check("aggregations")
class AggregationsCheck(BaseCheck):
    _METHODS = {"sum", "count", "avg", "min", "max", "distinct_count"}

    def _render_rule_sql(self, method: str, source_col: str | None, target_col: str | None) -> Tuple[str, str]:
        m = method.lower()
        if m not in self._METHODS:
            raise ValueError(f"Unsupported aggregation method: {method}")

        if m == "count":
            col_s = "*" if not source_col else source_col
            col_t = "*" if not target_col else target_col
            return f"COUNT({col_s})", f"COUNT({col_t})"

        if m == "distinct_count":
            if not source_col or not target_col:
                raise ValueError("distinct_count requires 'column' or both 'source_column' and 'target_column'")
            return f"COUNT(DISTINCT {source_col})", f"COUNT(DISTINCT {target_col})"

        if not source_col or not target_col:
            raise ValueError(f"{method} requires 'column' or both 'source_column' and 'target_column'")
        return f"{m.upper()}({source_col})", f"{m.upper()}({target_col})"

    def _compare(
        self, lhs: Any, rhs: Any, abs_tol: float | None, pct_tol: float | None
    ) -> bool:
        def _try_parse_datetime(val):
            if isinstance(val, datetime):
                return val.astimezone(timezone.utc) if val.tzinfo else val.replace(tzinfo=timezone.utc)
            if isinstance(val, str):
                try:
                    dt = dtparser.parse(val)
                    if not isinstance(dt, datetime):
                        return None
                    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except Exception:
                    return None
            return None

        lhs_dt, rhs_dt = _try_parse_datetime(lhs), _try_parse_datetime(rhs)
        if lhs_dt and rhs_dt:
            diff_min = abs((lhs_dt - rhs_dt).total_seconds()) / 60.0
            if abs_tol is not None and diff_min <= abs_tol:
                return True
            return diff_min < 0.000001

        try:
            lhs_f, rhs_f = float(lhs or 0.0), float(rhs or 0.0)
        except (TypeError, ValueError):
            return str(lhs).strip() == str(rhs).strip()

        diff = abs(lhs_f - rhs_f)
        if abs_tol is not None and diff <= abs_tol:
            return True
        if pct_tol is not None:
            base = max(abs(rhs_f), 1e-12)
            if (diff / base) * 100.0 <= pct_tol:
                return True
        return lhs_f == rhs_f

    def run(self) -> CheckResult:
        rules = self.check_cfg.rules or []
        if not rules:
            raise ValueError("aggregations requires 'rules'")

        source_select_sql = self.source.render_select_sql(self.table_cfg.source)
        target_select_sql = self.target.render_select_sql(self.table_cfg.target)

        order_by_source = self.check_cfg.order_by_source or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="source"
        )
        order_by_target = self.check_cfg.order_by_target or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="target"
        )

        source_data_sql = wrap_order_by(source_select_sql, order_by_source)
        target_data_sql = wrap_order_by(target_select_sql, order_by_target)

        results: List[Dict[str, Any]] = []
        all_pass = True

        for idx, r in enumerate(rules):
            method = r.get("method")
            source_col = r.get("source_column") or r.get("source_col")
            target_col = r.get("target_column") or r.get("target_col")
            column = r.get("column") or r.get("col")

            if column and not (source_col or target_col):
                source_col = target_col = column

            abs_tol = r.get("tolerance_abs", self.check_cfg.tolerance_abs)
            pct_tol = r.get("tolerance_pct", self.check_cfg.tolerance_pct)

            lhs_expr, rhs_expr = self._render_rule_sql(method, source_col, target_col)

            s_sql = f"SELECT {lhs_expr} AS v FROM ({source_data_sql}) q"
            t_sql = f"SELECT {rhs_expr} AS v FROM ({target_data_sql}) q"

            s_val = self.source.fetch_scalar(s_sql)
            t_val = self.target.fetch_scalar(t_sql)

            ok = self._compare(s_val, t_val, abs_tol, pct_tol)

            try:
                s_val = float(s_val) if isinstance(s_val, (int, float, str)) and str(s_val).replace('.', '', 1).isdigit() else s_val
                t_val = float(t_val) if isinstance(t_val, (int, float, str)) and str(t_val).replace('.', '', 1).isdigit() else t_val
            except Exception:
                pass

            entry = {
                "method": method,
                "column": column,
                "source_column": source_col,
                "target_column": target_col,
                "source": s_val,
                "target": t_val,
                "tolerance_abs": abs_tol,
                "tolerance_pct": pct_tol,
                "pass": ok,
            }

            if not ok:
                all_pass = False

            method_lower = str(method or "").lower()
            mismatch_cfg = _resolve_rule_sampling_cfg(r, self.check_cfg, self.table_cfg.name, idx)
            if not ok and method_lower in {"count", "distinct_count"} and mismatch_cfg:
                source_id, target_id = _resolve_rule_id_columns(r, self.check_cfg)
                mismatch_result = _maybe_sample_rule_mismatch(
                    self,
                    mismatch_cfg,
                    source_select_sql,
                    target_select_sql,
                    source_id,
                    target_id,
                    idx,
                    method or "count",
                )
                if mismatch_result:
                    entry["mismatch_ranges"] = mismatch_result.summary(mismatch_cfg.max_ranges)
                    self.record_mismatch_sampling(
                        f"{self.table_cfg.name}.aggregations[{idx}]",
                        mismatch_result,
                    )
                    if uri := self.persist_mismatch_csv(
                        f"{self.table_cfg.name}.aggregations[{idx}]",
                        mismatch_result,
                    ):
                        attach_csv_uri(entry, uri)

            results.append(
                {k: v for k, v in entry.items() if v not in (None, "", [], {})}
            )

        return CheckResult(
            table=self.table_cfg.name,
            check_type="aggregations",
            status="PASS" if all_pass else "FAIL",
            details={
                "rules": [
                    {k: v for k, v in rule.items() if v not in (None, "", [], {})}
                    for rule in results
                ]
            },
        )


def _resolve_rule_sampling_cfg(
    rule: Dict[str, Any], cfg: CheckCfg, table_name: str, rule_index: int
) -> Optional[MismatchSamplingCfg]:
    sampling = rule.get("mismatch_sampling")
    if sampling:
        if isinstance(sampling, MismatchSamplingCfg):
            return sampling
        try:
            return MismatchSamplingCfg.model_validate(sampling)
        except Exception as exc:
            log(
                "mismatch_sampling.invalid_config",
                level="ERROR",
                table=table_name,
                check="aggregations",
                rule_index=rule_index,
                error=str(exc),
            )
            return None
    return cfg.mismatch_sampling


def _resolve_rule_id_columns(
    rule: Dict[str, Any], cfg: CheckCfg
) -> Tuple[Optional[str], Optional[str]]:
    fallback = rule.get("id_column") or cfg.id_column
    return (
        rule.get("id_column_source") or cfg.id_column_source or fallback,
        rule.get("id_column_target") or cfg.id_column_target or fallback,
    )


def _maybe_sample_rule_mismatch(
    check: AggregationsCheck,
    sampling_cfg: MismatchSamplingCfg,
    source_base_sql: str,
    target_base_sql: str,
    source_id: Optional[str],
    target_id: Optional[str],
    rule_index: int,
    method: str,
) -> Optional[MismatchSamplingResult]:
    if not source_id or not target_id:
        log(
            "mismatch_sampling.skipped",
            table=check.table_cfg.name,
            check="aggregations",
            rule_index=rule_index,
            method=method,
            reason="missing_id_column",
        )
        return None

    try:
        return sample_mismatch_ranges(
            source=check.source,
            target=check.target,
            source_base_sql=source_base_sql,
            target_base_sql=target_base_sql,
            id_column_source=source_id,
            id_column_target=target_id,
            sampling_cfg=sampling_cfg,
        )
    except Exception as exc:
        log(
            "mismatch_sampling.error",
            level="ERROR",
            table=check.table_cfg.name,
            check="aggregations",
            rule_index=rule_index,
            method=method,
            error=str(exc),
        )
        return None
