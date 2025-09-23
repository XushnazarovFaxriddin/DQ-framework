from typing import Dict, List, Optional



def sanitize_identifier(name: str) -> str:
    """
    Produce a cross-dialect-safe identifier (no quoting required).
    Replaces non [A-Za-z0-9_] chars with _, and prefixes with c_ if starting with a digit.
    """
    safe = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            safe.append(ch)
        else:
            safe.append("_")
    if not safe:
        return "c_"
    if safe[0].isdigit():
        safe.insert(0, "c_")
    return "".join(safe)

def wrap_order_by(inner_sql: str, order_by_exprs: Optional[List[str]]) -> str:
    """
    Wrap a subquery with ORDER BY expressions (dialect-agnostic).
    The expressions must reference columns available from the inner_sql SELECT list.
    """
    if not order_by_exprs:
        return inner_sql
    clause = ", ".join(order_by_exprs)
    return f"SELECT * FROM ({inner_sql}) q ORDER BY {clause}"

def wrap_order_by_limit(inner_sql: str, order_by_exprs: Optional[List[str]], limit: Optional[int]) -> str:
    """
    Wrap with ORDER BY and LIMIT safely. LIMIT is applied only if provided (>0).
    """
    sql = wrap_order_by(inner_sql, order_by_exprs)
    if limit and int(limit) > 0:
        sql = f"SELECT * FROM ({sql}) qq LIMIT {int(limit)}"
    return sql


def build_aligned_select(base_sql: str, projections: Dict[str, str]) -> str:
    """
    Build an aligned SELECT:
      SELECT <expr_source> AS <canonical>, ...
      FROM (<base_sql>) AS q
    'projections' maps canonical_name -> expression (column or SQL expression).
    Assumes expressions reference columns as seen in base_sql's SELECT.
    """
    select_items = []
    for canon, expr in projections.items():
        alias = sanitize_identifier(canon)
        select_items.append(f"{expr} AS {alias}")
    select_clause = ", ".join(select_items) if select_items else "*"
    return f"SELECT {select_clause} FROM ({base_sql}) AS q"
