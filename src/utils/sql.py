"""SQL helper utilities used across connectors and checks."""

from __future__ import annotations

from typing import Dict, List, Optional


def sanitize_identifier(name: str) -> str:
    safe = []
    for char in name:
        if char.isalnum() or char == "_":
            safe.append(char)
        else:
            safe.append("_")
    if not safe:
        return "c_"
    if safe[0].isdigit():
        safe.insert(0, "c_")
    return "".join(safe)


def wrap_order_by(inner_sql: str, order_by_exprs: Optional[List[str]]) -> str:
    if not order_by_exprs:
        return inner_sql
    clause = ", ".join(order_by_exprs)
    return f"SELECT * FROM ({inner_sql}) q ORDER BY {clause}"


def wrap_order_by_limit(inner_sql: str, order_by_exprs: Optional[List[str]], limit: Optional[int], *, engine: str = "") -> str:
    if not order_by_exprs and not limit:
        return inner_sql

    ob_clause = f"ORDER BY {', '.join(order_by_exprs)}" if order_by_exprs else ""

    if engine == "mssql":
        if limit:
            # MSSQL OFFSET-FETCH syntax
            if not ob_clause:
                ob_clause = "ORDER BY (SELECT NULL)"
            return f"{inner_sql} {ob_clause} OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
        else:
            # Bare ORDER BY is invalid in MSSQL subqueries
            return inner_sql

    if limit:
        return f"{inner_sql} {ob_clause} LIMIT {limit}" if ob_clause else f"{inner_sql} LIMIT {limit}"
    return f"{inner_sql} {ob_clause}"



def build_aligned_select(base_sql: str, projections: Dict[str, str]) -> str:
    select_items = []
    for canonical, expr in projections.items():
        alias = sanitize_identifier(canonical)
        select_items.append(f"{expr} AS {alias}")
    select_clause = ", ".join(select_items) if select_items else "*"
    return f"SELECT {select_clause} FROM ({base_sql}) AS q"
