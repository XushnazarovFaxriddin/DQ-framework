"""Row count parity check."""

from __future__ import annotations

from typing import List, Optional

from src.checks.base import BaseCheck
from src.compiler.schema import ColumnMapEntry
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
from src.utils.sql import wrap_order_by


def _map_order_by(
    columns: Optional[List[str]],
    column_map: Optional[dict[str, ColumnMapEntry]],
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


@register_check("row_count")
class RowCountCheck(BaseCheck):
    def run(self) -> CheckResult:
        s_sql = self.source.render_select_sql(self.table_cfg.source)
        t_sql = self.target.render_select_sql(self.table_cfg.target)

        order_by_source = self.check_cfg.order_by_source or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="source"
        )
        order_by_target = self.check_cfg.order_by_target or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="target"
        )

        s_sql = wrap_order_by(s_sql, order_by_source)
        t_sql = wrap_order_by(t_sql, order_by_target)

        s_count_sql = self.source.render_count_sql(s_sql)
        t_count_sql = self.target.render_count_sql(t_sql)

        s_count = int(self.source.fetch_scalar(s_count_sql))
        t_count = int(self.target.fetch_scalar(t_count_sql))

        status = "PASS" if s_count == t_count else "FAIL"
        return CheckResult(
            table=self.table_cfg.name,
            check_type="row_count",
            status=status,
            details={"source_count": s_count, "target_count": t_count},
        )
