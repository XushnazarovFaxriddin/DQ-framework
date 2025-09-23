"""
High-level textual summary for email bodies or logs.
"""

from src.runtime.results import RunResult


def summarize_run(result: RunResult) -> str:
    passed = sum(c.status == "PASS" for c in result.checks)
    failed = sum(c.status == "FAIL" for c in result.checks)
    skipped = sum(c.status == "SKIP" for c in result.checks)
    lines = [
        f"Status: {result.overall_status}",
        f"Checks - PASS: {passed} | FAIL: {failed} | SKIP: {skipped}",
        ""
    ]
    if failed:
        lines.append("Failures:")
        for c in result.checks:
            if c.status == "FAIL":
                lines.append(f"- {c.table}/{c.check_type}: {str(c.details)[:200]}")
    else:
        lines.append("All checks passed.")
    return "\n".join(lines)
