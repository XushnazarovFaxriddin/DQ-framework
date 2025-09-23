"""Snowflake connector stub with deterministic hash expressions."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

import pandas as pd

from src.compiler.schema import HashingCfg, QueryCfg
from src.connectors.base import BaseConnector
from src.runtime.registry import register_connector

try:  # pragma: no cover - optional dependency
    from sqlalchemy import create_engine, text
except Exception:  # pragma: no cover
    create_engine = None
    text = None


@register_connector("snowflake")
class SnowflakeConnector(BaseConnector):
    engine_name = "snowflake"

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        if create_engine is None:
            self.engine = None
            return
        try:
            self.engine = create_engine(uri)
        except Exception as exc:  # pragma: no cover - depends on driver availability
            raise RuntimeError(
                "Failed to initialize Snowflake SQLAlchemy engine. Install snowflake-sqlalchemy and provide a valid URI."
            ) from exc

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
                "Snowflake connector requires QueryCfg.table when query is not provided"
            )
        return f'SELECT {sel} FROM "{q.table}"'

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql})"

    def _token_expr(self, col: str, hashing: HashingCfg) -> str:
        token = f"COALESCE(TO_VARCHAR({col}), '{hashing.null_token}')"
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

    def _md5_hex(self, expr: str) -> str:
        return f"LOWER(HEX_ENCODE(MD5(TO_BINARY({expr}))))"

    def _sha256_hex(self, expr: str) -> str:
        return f"LOWER(HEX_ENCODE(SHA2(TO_BINARY({expr}), 256)))"

    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        cols = list(cols)
        delim = hashing.delimiter.replace("'", "''")

        if hashing.algorithm == "double_md5":
            inner = [self._md5_hex(self._token_expr(c, hashing)) for c in cols]
            chain = self._concat(inner, delim)
            return self._md5_hex(chain)

        if hashing.algorithm == "md5_row":
            tokens = [self._token_expr(c, hashing) for c in cols]
            chain = self._concat(tokens, delim)
            return self._md5_hex(chain)

        if hashing.algorithm == "sha256_row":
            tokens = [self._token_expr(c, hashing) for c in cols]
            chain = self._concat(tokens, delim)
            return self._sha256_hex(chain)

        raise ValueError(
            f"Unsupported hashing algorithm for Snowflake: {hashing.algorithm}"
        )

    def fetch_df(self, sql: str) -> pd.DataFrame:
        if self.engine is None or text is None:
            raise RuntimeError("Snowflake SQL execution requires snowflake-sqlalchemy")
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    def fetch_scalar(self, sql: str) -> Any:
        if self.engine is None or text is None:
            raise RuntimeError("Snowflake SQL execution requires snowflake-sqlalchemy")
        with self.engine.connect() as conn:
            return conn.execute(text(sql)).scalar()

    def fetch_column(self, sql: str) -> List[Any]:
        if self.engine is None or text is None:
            raise RuntimeError("Snowflake SQL execution requires snowflake-sqlalchemy")
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
            return [row[0] for row in rows]

    def information_schema_columns(self, table_name: str) -> List[dict[str, Any]]:
        if self.engine is None or text is None:
            raise RuntimeError("Snowflake SQL execution requires snowflake-sqlalchemy")
        query = text(
            """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = :table
            ORDER BY ORDINAL_POSITION
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query, {"table": table_name.upper()}).mappings().all()
            return [dict(row) for row in rows]
