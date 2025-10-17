"""
Custom SQL Check (Universal Mode)
=================================

A highly flexible checker that can execute one or two arbitrary SQL queries
and validate their results using multiple comparison modes.

Supports:
- Single-query mode: run SQL on one connector (source/target) and check the result.
- Dual-query mode: run one SQL on source and another on target, compare results.
- Numeric, boolean, text, and JSON comparisons.
- Absolute/percentage tolerance for numeric results.
- Deep dict/list comparison for JSON results.
- Auto-inference of PASS/FAIL based on type and expectation.
"""

import datetime
import json
from typing import Any, Dict, Optional
from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.runtime.registry import register_check
from dateutil import parser as dtparser



@register_check("custom_sql")
class CustomSQLCheck(BaseCheck):
    def run(self) -> CheckResult:
        cfg = self.check_cfg

        # --- Mode selection ---
        mode = (cfg.mode or "single").lower()
        on = (cfg.on or "source").lower()

        sql_source = cfg.sql_source
        sql_target = cfg.sql_target
        sql = cfg.sql

        expect = cfg.expected_result
        compare_mode = (cfg.compare_mode or "equals").lower()
        tolerance_abs = cfg.tolerance_abs
        tolerance_pct = cfg.tolerance_pct
        tolerance_time_sec = cfg.tolerance_time_sec
        tolerance_time_min = cfg.tolerance_time_min

        if mode not in ["single", "dual"]:
            raise ValueError("custom_sql.mode must be 'single' or 'dual'")

        # --- Execute queries ---
        source_res = target_res = None

        if mode == "dual":
            if not sql_source or not sql_target:
                raise ValueError("dual mode requires both sql_source and sql_target")

            source_res = self.source.fetch_scalar(sql_source)
            target_res = self.target.fetch_scalar(sql_target)
        else:
            if not sql:
                raise ValueError("single mode requires 'sql'")
            connector = self.source if on == "source" else self.target
            source_res = connector.fetch_scalar(sql)

        # --- Comparison logic ---
        status = "PASS"
        def _to_datetime(val: Any) -> Optional[datetime.datetime]:
            if val is None:
                return None
            if isinstance(val, datetime.datetime):
                # Normalize timezone — convert to UTC if tzinfo present
                return val.astimezone(datetime.timezone.utc) if val.tzinfo else val.replace(tzinfo=datetime.timezone.utc)
            if isinstance(val, datetime.date):
                return datetime.datetime.combine(val, datetime.time.min, tzinfo=datetime.timezone.utc)
            if isinstance(val, str):
                try:
                    dt = dtparser.parse(val)
                    if not isinstance(dt, datetime.datetime):
                        return None
                    # Normalize tzinfo (make everything UTC)
                    if dt.tzinfo:
                        dt = dt.astimezone(datetime.timezone.utc)
                    else:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    return dt
                except Exception:
                    return None
            return None

        def _is_equal(a: Any, b: Any) -> bool:
            """Compare two arbitrary values with numeric, datetime, or text tolerance."""
            # --- Numeric comparison ---
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if tolerance_abs is not None and abs(a - b) <= tolerance_abs:
                    return True
                if tolerance_pct is not None:
                    base = max(abs(b), 1e-12)
                    if (abs(a - b) / base) * 100 <= tolerance_pct:
                        return True
                return a == b

            # Datetime comparison (robust)
            da, db = _to_datetime(a), _to_datetime(b)
            if da is not None and db is not None:
                diff = abs((da - db).total_seconds())
                if tolerance_time_sec is not None and diff <= tolerance_time_sec:
                    return True
                if tolerance_time_min is not None and diff <= tolerance_time_min * 60:
                    return True
                return False  # enforce strict fail otherwise

            # --- String / JSON comparison ---
            try:
                if isinstance(a, str) and isinstance(b, str):
                    return a.strip() == b.strip()
                if isinstance(a, (dict, list)) and isinstance(b, (dict, list)):
                    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
            except Exception:
                pass
            # --- Default equality ---
            return a == b

        # --- Evaluate ---
        if mode == "dual":
            # Dual-source comparison
            if compare_mode == "equals":
                if not _is_equal(source_res, target_res):
                    status = "FAIL"
            elif compare_mode == "greater":
                status = "PASS" if source_res > target_res else "FAIL"
            elif compare_mode == "less":
                status = "PASS" if source_res < target_res else "FAIL"
            else:
                raise ValueError(f"Unsupported compare_mode: {compare_mode}")
        else:
            # Single query evaluation
            result = source_res
            if isinstance(result, bool):
                status = "PASS" if result else "FAIL"
            elif isinstance(result, (int, float)):
                if expect is not None:
                    if not _is_equal(result, expect):
                        status = "FAIL"
                elif result != 0:
                    status = "FAIL"
            elif isinstance(result, str):
                # Try datetime / tolerant equality before plain string comparison
                if expect is not None:
                    if not _is_equal(result, expect):
                        status = "FAIL"
                else:
                    norm = result.strip().lower()
                    if norm in ("fail", "false", "error", "invalid"):
                        status = "FAIL"
            elif result is None:
                status = "FAIL"

        def _safe(val):
            if isinstance(val, datetime.datetime):
                return val.isoformat()
            return val


        # --- Details (dynamic and compact) ---
        details: Dict[str, Any] = {"mode": mode}

        if mode == "single":
            details["on"] = on
            details["sql"] = sql.strip()
            details["result"] = _safe(source_res)
            if expect is not None:
                details["expected_result"] = expect
        else:
            details["sql_source"] = sql_source.strip()
            details["sql_target"] = sql_target.strip()
            details["source_result"] = _safe(source_res)
            details["target_result"] = _safe(target_res)
            details["compare_mode"] = compare_mode

        if tolerance_abs or tolerance_pct:
            details["tolerance"] = {"abs": tolerance_abs, "pct": tolerance_pct}

        return CheckResult(
            table=self.table_cfg.name,
            check_type="custom_sql",
            status=status,
            details=details,
        )
