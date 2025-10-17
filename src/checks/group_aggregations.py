"""group_aggregations check — compares aggregates per partition key (group-by) with full tolerance and column mapping support."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from src.checks.base import BaseCheck
from src.compiler.schema import ColumnMapEntry
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
from src.utils.sql import build_aligned_select, wrap_order_by
from src.utils.logger import log


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


@register_check("group_aggregations")
class GroupAggregationsCheck(BaseCheck):
    _METHODS = {"count", "sum", "avg", "min", "max", "distinct_count"}

    def _render_rule_sql(self, method: str, source_col: str | None, target_col: str | None) -> Tuple[str, str]:
        """Build aggregate SQL expressions for source/target based on method."""
        m = method.lower()
        if m not in self._METHODS:
            raise ValueError(f"Unsupported aggregation method: {method}")

        if m == "count":
            col_s = "*" if not source_col else source_col
            col_t = "*" if not target_col else target_col
            return f"COUNT({col_s})", f"COUNT({col_t})"

        if m == "distinct_count":
            if not source_col or not target_col:
                raise ValueError("distinct_count requires both 'source_column' and 'target_column'")
            return f"COUNT(DISTINCT {source_col})", f"COUNT(DISTINCT {target_col})"

        if not source_col or not target_col:
            raise ValueError(f"{method} requires both 'source_column' and 'target_column'")
        return f"{m.upper()}({source_col})", f"{m.upper()}({target_col})"

    def _compare(self, lhs: float, rhs: float, abs_tol: float | None, pct_tol: float | None) -> bool:
        diff = abs(lhs - rhs)
        if abs_tol is not None and diff <= abs_tol:
            return True
        if pct_tol is not None:
            base = max(abs(rhs), 1e-12)
            if (diff / base) * 100.0 <= pct_tol:
                return True
        return lhs == rhs

    def run(self) -> CheckResult:
        rules = self.check_cfg.rules or [
            {
                "method": getattr(self.check_cfg, "method", "count"),
                "column": getattr(self.check_cfg, "column", None),
                "source_column": getattr(self.check_cfg, "source_column", None),
                "target_column": getattr(self.check_cfg, "target_column", None),
            }
        ]
        top_n = int(getattr(self.check_cfg, "top_n", 50))

        # Partition key resolution
        if self.check_cfg.include_map:
            if len(self.check_cfg.include_map) != 1:
                raise ValueError("group_aggregations.include_map must contain exactly one entry defining the partition key")
            canon = next(iter(self.check_cfg.include_map.keys()))
            s_part = self.check_cfg.include_map[canon].source
            t_part = self.check_cfg.include_map[canon].target
        else:
            if (
                self.table_cfg.column_map
                and self.check_cfg.include
                and len(self.check_cfg.include) == 1
            ):
                canon = self.check_cfg.include[0]
                if canon not in self.table_cfg.column_map:
                    raise ValueError(f"partition canonical '{canon}' not found in table.column_map")
                s_part = self.table_cfg.column_map[canon].source
                t_part = self.table_cfg.column_map[canon].target
            else:
                raise ValueError("group_aggregations requires a single partition key via include_map or table.column_map + include[1]")

        # Base SQL rendering
        s_base = self.source.render_select_sql(self.table_cfg.source)
        t_base = self.target.render_select_sql(self.table_cfg.target)

        order_by_source = self.check_cfg.order_by_source or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="source"
        )
        order_by_target = self.check_cfg.order_by_target or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="target"
        )

        s_base = wrap_order_by(s_base, order_by_source)
        t_base = wrap_order_by(t_base, order_by_target)

        s_sql = build_aligned_select(s_base, {"p": s_part})
        t_sql = build_aligned_select(t_base, {"p": t_part})

        results: List[Dict[str, Any]] = []
        all_pass = True

        for r in rules:
            method = r.get("method")
            source_col = r.get("source_column") or r.get("source_col")
            target_col = r.get("target_column") or r.get("target_col")
            column = r.get("column") or r.get("col")

            if column and not (source_col or target_col):
                source_col = target_col = column

            abs_tol = r.get("tolerance_abs", self.check_cfg.tolerance_abs)
            pct_tol = r.get("tolerance_pct", self.check_cfg.tolerance_pct)

            s_expr, t_expr = self._render_rule_sql(method, source_col, target_col)

            s_group = f"SELECT p, {s_expr} AS v FROM ({s_sql}) q GROUP BY p"
            t_group = f"SELECT p, {t_expr} AS v FROM ({t_sql}) q GROUP BY p"

            s_rows = self.source.fetch_df(s_group)
            t_rows = self.target.fetch_df(t_group)

            s_map = {r["p"]: float(r["v"]) for _, r in s_rows.iterrows()}
            t_map = {r["p"]: float(r["v"]) for _, r in t_rows.iterrows()}

            diffs: List[Dict[str, Any]] = []
            for k in sorted(set(s_map.keys()).union(t_map.keys())):
                sv = s_map.get(k)
                tv = t_map.get(k)
                if sv is None or tv is None:
                    diffs.append({"partition": k, "source": sv, "target": tv})
                    continue
                ok = self._compare(sv, tv, abs_tol, pct_tol)
                if not ok:
                    diffs.append({"partition": k, "source": sv, "target": tv})
                    if len(diffs) >= top_n:
                        break

            result_entry = {
                "method": method,
                "column": column,
                "source_column": source_col,
                "target_column": target_col,
                "tolerance_abs": abs_tol,
                "tolerance_pct": pct_tol,
                "diff_sample": diffs[:top_n],
                "failed_partitions": len(diffs),
                "pass": ok
            }
            results.append({k: v for k, v in result_entry.items() if v not in (None, "", [], {})})

            if diffs:
                all_pass = False

        return CheckResult(
            table=self.table_cfg.name,
            check_type="group_aggregations",
            status="PASS" if all_pass else "FAIL",
            details={"rules": results},
        )
