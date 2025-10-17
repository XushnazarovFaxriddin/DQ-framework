
from typing import Any, Dict
import yaml


def _yaml_inline(obj: Dict[str, Any], max_chars: int = 1200) -> str:
    try:
        s = yaml.safe_dump(obj, sort_keys=False, allow_unicode=True).strip()
    except Exception:
        s = str(obj)
    s = s.replace("\n", "<br/>").replace("|", r"\|")
    if len(s) > max_chars:
        s = s[:max_chars] + " ..."
    return s

def _html_inline(obj: Dict[str, Any], max_chars: int = 1200) -> str:
    yaml_str = _yaml_inline(obj, max_chars)
    rows = yaml_str.split("<br/>")
    result = ""
    for row in rows:
        result += f"<li>{row}</li>"
    return f"<ul>{result}</ul>"


def _norm_cols(rule: Dict[str, Any]) -> Dict[str, Any]:
    norm = dict(rule)  # copy all fields dynamically
    col = rule.get("column") or rule.get('col')
    sc = rule.get("source_column") or rule.get('source_col')
    tc = rule.get("target_column") or rule.get('target_col')

    if col:
        norm["column"] = col
    elif sc or tc:
        norm["column"] = f"{sc} → {tc}"
    norm.pop('col', None)
    norm.pop('source_column', None)
    norm.pop('source_col', None)
    norm.pop('target_column', None)
    norm.pop('target_col', None)
    return norm
