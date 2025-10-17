"""
High-level textual summary for email bodies or logs.
"""

from typing import Any, Dict
from src.runtime.results import RunResult


def summarize_run(result: RunResult, *, vars_map: Dict[str, Any] | None = None) -> str:
    max_chars = int((vars_map or {}).get("max_details_chars", 2000))
    passed = sum(c.status == "PASS" for c in result.checks)
    failed = sum(c.status == "FAIL" for c in result.checks)
    skipped = sum(c.status == "SKIP" for c in result.checks)
    lines = [
        f"Status: {result.overall_status}",
        f"Checks - PASS: {passed} | FAIL: {failed} | SKIP: {skipped}",
        "",
    ]
    if failed:
        lines.append("Failures:")
        for c in result.checks:
            if c.status != "FAIL":
                continue

            if str(c.check_type).endswith("aggregations") and isinstance(c.details, dict):
                rules = c.details.get("rules", [])
                for r in rules:
                    method = r.get("method", "?")
                    lines.append(
                        f"- {c.table}/aggregation[{method}]: {str(r)[:max_chars]}{' ...' if len(str(r)) > max_chars else ''}"
                    )
            else:
                details_str = str(c.details)
                lines.append(
                    f"- {c.table}/{c.check_type}: {details_str[:max_chars]}{' ...' if len(details_str) > max_chars else ''}"
                )
    else:
        lines.append("All checks passed.")
    return "\n".join(lines)
