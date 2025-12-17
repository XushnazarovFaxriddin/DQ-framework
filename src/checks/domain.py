"""
Domain Check (single mode)
- Validates column values within a single source or target dataset.
- Supports allowed_values, exclude_values (not_null), regex, numeric/date range.
- `on:` parameter defines which side (source or target) to query.
- Multi-engine compatible (BigQuery, Snowflake, Postgres, Oracle, MSSQL).
- Dynamically includes only relevant details.
"""

from typing import Any, List, Optional
import pandas as pd

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.runtime.registry import register_check


@register_check("domain")
class DomainCheck(BaseCheck):
    def run(self) -> CheckResult:
        col = self.check_cfg.column or self.check_cfg.col
        on = str(self.check_cfg.on).lower()
        # Select connector based on 'on' value
        if on not in ["source", "target"]:
            raise ValueError("domain check: 'on' must be either 'source' or 'target'")
        connector = self.source if on == "source" else self.target
        base_sql = connector.render_select_sql(
            self.table_cfg.source if on == "source" else self.table_cfg.target
        )

        # Extract config
        allowed_values = set(self.check_cfg.allowed_values or self.check_cfg.include_values or [])
        exclude_values = set(self.check_cfg.exclude_values or [])
        regex_pattern = self.check_cfg.regex
        min_val = self.check_cfg.min
        max_val = self.check_cfg.max
        tolerance_abs = self.check_cfg.tolerance_abs or 0
        tolerance_pct = self.check_cfg.tolerance_pct or 0.0

        # Build WHERE clauses
        where_clauses = []

        # Range
        if min_val is not None:
            where_clauses.append(f"{col} < {min_val}")
        if max_val is not None:
            where_clauses.append(f"{col} > {max_val}")

        # Allowed values
        if allowed_values:
            vals = ", ".join([f"'{v}'" for v in allowed_values if v is not None])
            null_allowed = any(v is None for v in allowed_values)
            clause = f"{col} NOT IN ({vals})" if vals and len(vals) > 0  else ""
            if null_allowed:
                clause += f" AND {col} IS NOT NULL" if vals and len(vals) > 0  else f"{col} IS NOT NULL"
            where_clauses.append(clause)

        # Excluded values (for not_null)
        if exclude_values:
            vals = ", ".join([f"'{v}'" for v in exclude_values if v is not None])
            null_excluded = any(v is None for v in exclude_values)
            clause = f"{col} IN ({vals})" if vals and len(vals) > 0  else ""
            if null_excluded:
                clause += f" OR {col} IS NULL" if vals and len(vals) > 0  else f"{col} IS NULL"
            where_clauses.append(clause)

        # Regex validation
        if regex_pattern:
            engine = connector.engine_name
            if engine in ["bigquery", "snowflake"]:
                where_clauses.append(f"NOT REGEXP_CONTAINS(CAST({col} AS STRING), r'{regex_pattern}')")
            elif engine == "postgres":
                where_clauses.append(f"NOT ({col} ~ '{regex_pattern}')")
            elif engine in ["oracle", "mssql"]:
                where_clauses.append(f"NOT REGEXP_LIKE({col}, '{regex_pattern}')")
            # elif engine == "mssql":
            #     where_clauses.append(f"{col} NOT LIKE '{regex_pattern}'")
            else:
                where_clauses.append("1=1 /* regex unsupported */")

        invalid_clause = " OR ".join(where_clauses) if where_clauses else "1=0"

        # Query invalid and total counts
        invalid_sql = f"SELECT COUNT(*) FROM ({base_sql}) q WHERE {invalid_clause}"
        total_sql = f"SELECT COUNT(*) FROM ({base_sql}) q"

        invalid_count = connector.fetch_scalar(invalid_sql)
        total_count = max(1, connector.fetch_scalar(total_sql))
        invalid_pct = (invalid_count / total_count) * 100

        # Status
        status = "PASS" if (invalid_count <= tolerance_abs or invalid_pct <= tolerance_pct) else "FAIL"    

        # Dynamic details
        details = {"column": col, "on": on}
        if invalid_count > 0 or status == "FAIL":
            details["invalid_count"] = invalid_count
            details["invalid_pct"] = round(invalid_pct, 2)
            details["total_count"] = total_count
        if allowed_values:
            details["allowed_values"] = list(allowed_values)
        if exclude_values:
            details["excluded_values"] = list(exclude_values)
        if regex_pattern:
            details["regex"] = regex_pattern
        if min_val is not None or max_val is not None:
            details["range"] = {"min": min_val, "max": max_val}
        if tolerance_abs or tolerance_pct:
            details["tolerance"] = {"abs": tolerance_abs, "pct": tolerance_pct}

        return CheckResult(
            table=self.table_cfg.name,
            check_type="domain",
            status=status,
            details=details,
        )
