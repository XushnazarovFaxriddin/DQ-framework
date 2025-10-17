"""
Tabular text renderers: Markdown/ASCII summaries for alerts or logs.
- Uses YAML for details, rendered inline (no newlines) to avoid breaking markdown tables.
- For 'aggregations', expands each rule into its own row with Check = aggregations[method].
- Details length can be limited by config vars_map['max_details_chars'] (default 1200).
"""

from __future__ import annotations
from typing import Any, Dict, List
from src.runtime.results import RunResult
from src.utils.formatter import _yaml_inline, _norm_cols


def markdown_summary_table(result: RunResult, *, max_rows: int = 50, vars_map: Dict[str, Any] | None = None) -> str:
    max_chars = int((vars_map or {}).get("max_details_chars", 1200))

    lines: List[str] = ["| Table | Check | Status | Details |", "|---|---|---|---|"]
    row_count = 0

    for c in result.checks:
        if row_count >= max_rows:
            break

        # Aggregations expanded per rule
        if str(c.check_type).endswith("aggregations") and isinstance(c.details, dict) and "rules" in c.details:
            for r in c.details.get("rules", []):
                if row_count >= max_rows:
                    break
                check_name = f"{c.check_type}[{r.get('method')}]"
                norm = _norm_cols(r)
                details_str = _yaml_inline(norm, max_chars=max_chars)
                status = "PASS" if bool(r.get("pass")) else "FAIL"
                lines.append(f"| {c.table} | {check_name} | {status} | {details_str} |")
                row_count += 1
            continue

        # Default: show details inline
        details_str = _yaml_inline(c.details if isinstance(c.details, dict) else {"details": c.details}, max_chars=max_chars)
        lines.append(f"| {c.table} | {c.check_type} | {c.status} | {details_str} |")
        row_count += 1

    return "\n".join(lines)
