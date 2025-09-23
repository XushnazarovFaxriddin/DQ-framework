"""
Row count check:
- Counts rows on both sides using rendered SELECTs.
- Mapping is not required since we only count rows.
"""

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.runtime.registry import register_check

@register_check("row_count")
class RowCountCheck(BaseCheck):
    def run(self) -> CheckResult:
        s_sql = self.source.render_select_sql(self.table_cfg.source)
        t_sql = self.target.render_select_sql(self.table_cfg.target)

        s_count_sql = self.source.render_count_sql(s_sql)
        t_count_sql = self.target.render_count_sql(t_sql)

        s_count = int(self.source.fetch_scalar(s_count_sql))
        t_count = int(self.target.fetch_scalar(t_count_sql))

        status = "PASS" if s_count == t_count else "FAIL"
        return CheckResult(
            table=self.table_cfg.name,
            check_type="row_count",
            status=status,
            details={"source_count": s_count, "target_count": t_count}
        )
