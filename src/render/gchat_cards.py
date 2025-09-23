"""
Google Chat Card renderer:
- Builds a compact card summarizing run status and failed checks.
- Use with alerts.gchat when route.mode == "card".
"""

from typing import List, Dict, Any
from src.runtime.results import RunResult


def build_run_card(result: RunResult, *, max_items: int = 20) -> Dict[str, Any]:
    failures = [c for c in result.checks if c.status == "FAIL"]
    header = {
        "title": f"DQF Run — {result.overall_status}",
        "subtitle": f"Failures: {len(failures)} | Total checks: {len(result.checks)}",
    }

    sections = []
    if failures:
        widgets = []
        for c in failures[:max_items]:
            widgets.append({
                "keyValue": {
                    "topLabel": f"{c.table} / {c.check_type}",
                    "content": f"Status: {c.status}",
                    "contentMultiline": True,
                    "bottomLabel": str(c.details)[:300],
                }
            })
        sections.append({"widgets": widgets})
    else:
        sections.append({"widgets": [{"textParagraph": {"text": "All checks passed ✔"}}]})

    return {
        "cards": [
            {
                "header": header,
                "sections": sections
            }
        ]
    }
