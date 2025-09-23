"""
Tabular text renderers: Markdown/ASCII summaries for alerts or logs.
"""

from src.runtime.results import RunResult


def markdown_summary_table(result: RunResult, *, max_rows: int = 30) -> str:
    lines = ["| Table | Check | Status | Details |", "|---|---|---|---|"]
    for c in result.checks[:max_rows]:
        lines.append(
            f"| {c.table} | {c.check_type} | {c.status} | `{str(c.details)[:120]}` |"
        )
    return "\n".join(lines)
