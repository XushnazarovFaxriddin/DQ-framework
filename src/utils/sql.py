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


def wrap_order_by_limit(
    inner_sql: str, order_by_exprs: Optional[List[str]], limit: Optional[int]
) -> str:
    sql = wrap_order_by(inner_sql, order_by_exprs)
    if limit and int(limit) > 0:
        sql = f"SELECT * FROM ({sql}) qq LIMIT {int(limit)}"
    return sql


def build_aligned_select(base_sql: str, projections: Dict[str, str]) -> str:
    select_items = []
    for canonical, expr in projections.items():
        alias = sanitize_identifier(canonical)
        select_items.append(f"{expr} AS {alias}")
    select_clause = ", ".join(select_items) if select_items else "*"
    return f"SELECT {select_clause} FROM ({base_sql}) AS q"
