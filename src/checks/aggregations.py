"""Aggregations check."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.checks.base import BaseCheck
from src.compiler.schema import ColumnMapEntry
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
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

    def _render_rule_sql(self, method: str, column: str | None) -> Tuple[str, str]:
        m = method.lower()
        if m not in self._METHODS:
            raise ValueError(f"Unsupported aggregation method: {method}")
        if m == "count":
            col = "*" if not column or column.strip() == "" else column
            return f"COUNT({col})", f"COUNT({col})"
        if m == "distinct_count":
            if not column:
                raise ValueError("distinct_count requires 'column'")
            return f"COUNT(DISTINCT {column})", f"COUNT(DISTINCT {column})"
        if not column:
            raise ValueError(f"{method} requires 'column'")
        return f"{m.upper()}({column})", f"{m.upper()}({column})"

    def _compare(
        self, lhs: float, rhs: float, abs_tol: float | None, pct_tol: float | None
    ) -> bool:
        diff = abs(lhs - rhs)
        if abs_tol is not None and diff <= abs_tol:
            return True
        if pct_tol is not None:
            base = max(abs(rhs), 1e-12)
            if (diff / base) * 100.0 <= pct_tol:
                return True
        return lhs == rhs

    def run(self) -> CheckResult:
        rules = self.check_cfg.rules or []
        if not rules:
            raise ValueError("aggregations requires 'rules'")

        s_sql_base = self.source.render_select_sql(self.table_cfg.source)
        t_sql_base = self.target.render_select_sql(self.table_cfg.target)

        order_by_source = self.check_cfg.order_by_source or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="source"
        )
        order_by_target = self.check_cfg.order_by_target or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="target"
        )

        s_sql_base = wrap_order_by(s_sql_base, order_by_source)
        t_sql_base = wrap_order_by(t_sql_base, order_by_target)

        results: List[Dict[str, Any]] = []
        all_pass = True

        for r in rules:
            method = r.get("method")
            column = r.get("column") or r.get("col")
            abs_tol = r.get("tolerance_abs", self.check_cfg.tolerance_abs)
            pct_tol = r.get("tolerance_pct", self.check_cfg.tolerance_pct)

            lhs_expr, rhs_expr = self._render_rule_sql(method, column)

            s_sql = f"SELECT {lhs_expr} AS v FROM ({s_sql_base}) q"
            t_sql = f"SELECT {rhs_expr} AS v FROM ({t_sql_base}) q"

            s_val = float(self.source.fetch_scalar(s_sql) or 0.0)
            t_val = float(self.target.fetch_scalar(t_sql) or 0.0)

            ok = self._compare(s_val, t_val, abs_tol, pct_tol)
            results.append(
                {
                    "method": method,
                    "column": column,
                    "source": s_val,
                    "target": t_val,
                    "tolerance_abs": abs_tol,
                    "tolerance_pct": pct_tol,
                    "pass": ok,
                }
            )
            if not ok:
                all_pass = False

        return CheckResult(
            table=self.table_cfg.name,
            check_type="aggregations",
            status="PASS" if all_pass else "FAIL",
            details={"rules": results},
        )
