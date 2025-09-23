"""Partitions check comparing aggregates per partition key."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.checks.base import BaseCheck
from src.compiler.schema import ColumnMapEntry
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
from src.utils.sql import build_aligned_select, wrap_order_by


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


@register_check("partitions")
class PartitionsCheck(BaseCheck):
    _METHODS = {"count", "sum", "avg", "min", "max", "distinct_count"}

    def _render_agg(self, method: str, column: str | None) -> str:
        m = method.lower()
        if m not in self._METHODS:
            raise ValueError(f"Unsupported method: {method}")
        if m == "count":
            col = "*" if not column else column
            return f"COUNT({col})"
        if m == "distinct_count":
            if not column:
                raise ValueError("distinct_count requires 'column'")
            return f"COUNT(DISTINCT {column})"
        if not column:
            raise ValueError(f"{method} requires 'column'")
        return f"{m.upper()}({column})"

    def run(self) -> CheckResult:
        method = getattr(self.check_cfg, "method", "count")
        column = getattr(self.check_cfg, "column", None)
        top_n = int(getattr(self.check_cfg, "top_n", 50))

        if self.check_cfg.include_map:
            if len(self.check_cfg.include_map) != 1:
                raise ValueError(
                    "partitions.include_map must contain exactly one entry defining the partition key"
                )
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
                    raise ValueError(
                        f"partition canonical '{canon}' not found in table.column_map"
                    )
                s_part = self.table_cfg.column_map[canon].source
                t_part = self.table_cfg.column_map[canon].target
            else:
                raise ValueError(
                    "partitions requires a single partition key via include_map or table.column_map + include[1]"
                )

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

        s_agg = self._render_agg(method, column)
        t_agg = self._render_agg(method, column)

        s_group = f"SELECT p, {s_agg} AS v FROM ({s_sql}) q GROUP BY p"
        t_group = f"SELECT p, {t_agg} AS v FROM ({t_sql}) q GROUP BY p"

        s_rows = self.source.fetch_df(s_group)
        t_rows = self.target.fetch_df(t_group)

        s_map = {r["p"]: float(r["v"]) for _, r in s_rows.iterrows()}
        t_map = {r["p"]: float(r["v"]) for _, r in t_rows.iterrows()}

        keys = sorted(set(s_map.keys()).union(t_map.keys()))
        diffs: List[Dict[str, Any]] = []
        for k in keys:
            sv = s_map.get(k)
            tv = t_map.get(k)
            if sv != tv:
                diffs.append({"partition": k, "source": sv, "target": tv})
                if len(diffs) >= top_n:
                    break

        status = "PASS" if not diffs else "FAIL"
        return CheckResult(
            table=self.table_cfg.name,
            check_type="partitions",
            status=status,
            details={
                "method": method,
                "column": column,
                "diff_sample": diffs[:top_n],
                "source_total_partitions": len(s_map),
                "target_total_partitions": len(t_map),
            },
        )
