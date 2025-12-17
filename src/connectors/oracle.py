"""Oracle connector using SQLAlchemy."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

import pandas as pd
from sqlalchemy import create_engine, text

from src.compiler.schema import HashingCfg, QueryCfg
from src.connectors.base import BaseConnector
from src.runtime.registry import register_connector


@register_connector("oracle")
class OracleConnector(BaseConnector):
    engine_name = "oracle"

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        try:
            self.engine = create_engine(uri, pool_pre_ping=True, future=True)
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize Oracle connector: {exc}") from exc

    def render_select_sql(
        self, q: QueryCfg, *, columns: Optional[List[str]] = None
    ) -> str:
        if q.query:
            return q.query
        sel = q.select.strip() if q.select else "*"
        if columns and not q.select:
            sel = ", ".join(columns)
        if not q.table:
            raise ValueError(
                "Oracle connector requires QueryCfg.table when query is not provided"
            )
        return f"SELECT {sel} FROM {q.table}"

    def wrap_subquery(self, sql: str, alias: str) -> str:
        return f"({sql}) {alias}"

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql})"

    def _token_expr(self, col: str, hashing: HashingCfg) -> str:
        token = f"NVL(TO_CHAR({col}), '{hashing.null_token}')"
        if hashing.case == "lower":
            token = f"LOWER({token})"
        elif hashing.case == "upper":
            token = f"UPPER({token})"
        return token

    def _concat(self, exprs: Iterable[str], delim: str) -> str:
        expr_list = list(exprs)
        if not expr_list:
            return "''"
        chain = expr_list[0]
        for expr in expr_list[1:]:
            chain = f"{chain} || '{delim}' || {expr}"
        return chain

    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        cols = list(cols)
        delim = hashing.delimiter.replace("'", "''")

        if hashing.algorithm == "double_md5":
            inner = [
                f"LOWER(STANDARD_HASH({self._token_expr(c, hashing)}, 'MD5'))"
                for c in cols
            ]
            chain = self._concat(inner, delim)
            return f"LOWER(STANDARD_HASH({chain}, 'MD5'))"

        if hashing.algorithm == "md5_row":
            tokens = [self._token_expr(c, hashing) for c in cols]
            chain = self._concat(tokens, delim)
            return f"LOWER(STANDARD_HASH({chain}, 'MD5'))"

        if hashing.algorithm == "sha256_row":
            tokens = [self._token_expr(c, hashing) for c in cols]
            chain = self._concat(tokens, delim)
            return f"LOWER(STANDARD_HASH({chain}, 'SHA256'))"

        raise ValueError(
            f"Unsupported hashing algorithm for Oracle: {hashing.algorithm}"
        )

    def fetch_df(self, sql: str) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    def fetch_scalar(self, sql: str) -> Any:
        with self.engine.connect() as conn:
            return conn.execute(text(sql)).scalar()

    def fetch_column(self, sql: str) -> List[Any]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
            return [row[0] for row in rows]

    def information_schema_columns(self, table_name: str) -> List[dict[str, Any]]:
        query = text(
            """
            SELECT COLUMN_NAME, DATA_TYPE, NULLABLE
            FROM ALL_TAB_COLUMNS
            WHERE TABLE_NAME = :table
            ORDER BY COLUMN_ID
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"table": table_name.upper()}).mappings().all()
            return [dict(row) for row in rows]
