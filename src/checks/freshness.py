"""
Freshness check:
- Measures lag based on max(<timestamp_column>) on source or target.
- Compares 'now' (UTC) with latest timestamp and fails if lag_minutes > max_lag_minutes.
- Config:
    type: freshness
    column: updated_at        # required
    on: source | target       # default: source
    max_lag_minutes: 60       # required
"""

from datetime import datetime, timezone
from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.runtime.registry import register_check

@register_check("freshness")
class FreshnessCheck(BaseCheck):
    def run(self) -> CheckResult:
        column = getattr(self.check_cfg, "column", None) or getattr(self.check_cfg, "col", None)
        if not column:
            raise ValueError("freshness requires 'column'")
        max_lag = self.check_cfg.max_lag_minutes
        if max_lag is None:
            raise ValueError("freshness requires 'max_lag_minutes'")
        side = getattr(self.check_cfg, "on", "source")

        base_sql = None
        connector = None
        if side == "source":
            base_sql = self.source.render_select_sql(self.table_cfg.source)
            connector = self.source
        elif side == "target":
            base_sql = self.target.render_select_sql(self.table_cfg.target)
            connector = self.target
        else:
            raise ValueError("freshness 'on' must be 'source' or 'target'")

        sql = f"SELECT MAX({column}) AS mx FROM ({base_sql}) q"
        latest = connector.fetch_scalar(sql)
        now = datetime.now(timezone.utc)

        try:
            # Try to normalize to datetime; connectors may return native types
            if hasattr(latest, "tzinfo"):
                latest_dt = latest if latest.tzinfo else latest.replace(tzinfo=timezone.utc)
            else:
                latest_dt = datetime.fromisoformat(str(latest)).replace(tzinfo=timezone.utc)
        except Exception:
            # As last resort, treat as naive and set UTC
            latest_dt = datetime.fromisoformat(str(latest))
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)

        lag_minutes = (now - latest_dt).total_seconds() / 60.0
        status = "PASS" if lag_minutes <= float(max_lag) else "FAIL"

        return CheckResult(
            table=self.table_cfg.name,
            check_type="freshness",
            status=status,
            details={
                "on": side,
                "column": column,
                "latest": latest_dt.isoformat(),
                "now_utc": now.isoformat(),
                "lag_minutes": lag_minutes,
                "max_lag_minutes": max_lag,
            }
        )
