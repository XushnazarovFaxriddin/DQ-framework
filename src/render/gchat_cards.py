"""
Google Chat Card renderer:
- Builds a compact card summarizing run status and failed checks.
- Use with alerts.gchat when route.mode == "card".
"""

from typing import Dict, Any
from src.runtime.results import RunResult
from src.utils.formatter import _html_inline, _yaml_inline, _norm_cols


def build_run_card(result, *, max_items: int = 50, send_only_fails: bool = True) -> dict:
    failures = [c for c in result.checks if c.status == "FAIL"]

    header = {
        "title": f"📊 DQF Validation Summary — {result.overall_status}",
        "subtitle": f"❌ Failures: {len(failures)} | ✅ Total Checks: {len(result.checks)}"
    }


    if not failures:
        return {
            "cardsV2": [
                {
                    "cardId": "run_summary",
                    "card": {
                        "header": header,
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "textParagraph": {
                                            "text": "🎉 <b>All checks passed successfully!</b><br>Everything looks great ✅"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }

    widgets = []
    checks = failures if send_only_fails else result.checks
    old_table_name = None
    for i, c in enumerate(checks[:max_items], start=1):
        if old_table_name is None:
            old_table_name = c.table
        if old_table_name != c.table:
            widgets.append({ "divider": {} })
        # Aggregations expanded per rule
        if str(c.check_type).endswith("aggregations") and isinstance(c.details, dict) and "rules" in c.details:
            rules = c.details.get("rules", [])
            if send_only_fails:
                rules = [rule for rule in rules if not bool(rule.get("pass"))]
            for j, r in enumerate(rules, start=1):
                check_name = f"{c.check_type}[{r.get('method')}]"
                norm = _norm_cols(r)
                details_str = _html_inline(norm)
                status = "✅ PASS" if bool(r.get("pass")) else "❌ FAIL"       
                text = (
                    f"<b>#{i}.{j}. Table:</b> {c.table}<br>"
                    f"<b>Check Type:</b> {check_name}<br>"
                    f"<b>Status:</b> {status}<br>"
                    f"<b>Details:</b> <br>{str(details_str)}<br>"
                    f"<hr>"
                )
                widgets.append({"textParagraph": {"text": text}})
        else:
            # Default: show details inline
            details_str = _html_inline(c.details if isinstance(c.details, dict) else {"details": c.details})
            text = (
                f"<b>#{i}. Table:</b> {c.table}<br>"
                f"<b>Check Type:</b> {c.check_type}<br>"
                f"<b>Status:</b> {f'❌ {str(c.status).upper()}' if str(c.status) != 'PASS' else '✅ PASS'}<br>"
                f"<b>Details:</b> {str(details_str)}<br><br>"
                f"<hr>"
            )
            widgets.append({"textParagraph": {"text": text}})

    return {
        "cardsV2": [
            {
                "cardId": "run_summary",
                "card": {
                    "header": header,
                    "sections": [
                        {
                            "header": "🚨 Failed Validations",
                            "widgets": widgets
                        }
                    ]
                }
            }
        ]
    }