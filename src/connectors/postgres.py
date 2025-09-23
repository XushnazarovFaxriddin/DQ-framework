"""
Postgres connector using SQLAlchemy.

Hashing notes:
- We normalize values via COALESCE(col::text, '<null_token>').
- Case folding is applied via lower()/upper() when requested.
- Algorithms:
  * double_md5 (default): md5(concat_ws(delim, md5(token1), md5(token2), ...))
  * md5_row: md5(concat_ws(delim, token1, token2, ...))
  * sha256_row: encode(digest(concat_ws(delim, token...), 'sha256'), 'hex')  # requires pgcrypto
- Output is LOWER hex to be comparable with BigQuery (which we downcase there as well).
"""

from typing import Iterable, List, Optional, Any
import pandas as pd
from sqlalchemy import create_engine, text

from src.connectors.base import BaseConnector
from src.runtime.registry import register_connector
from src.compiler.schema import QueryCfg, HashingCfg


@register_connector("postgres")
class PostgresConnector(BaseConnector):
    engine_name = "postgres"

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        self.engine = create_engine(uri, pool_pre_ping=True, future=True)

    # ----- SQL rendering -----
    def render_select_sql(
        self, q: QueryCfg, *, columns: Optional[List[str]] = None
    ) -> str:
        if q.query:
            return q.query
        sel = q.select.strip() if q.select else "*"
        if columns and not q.select:
            sel = ", ".join(columns)
        if not q.table:
            raise ValueError("QueryCfg requires 'table' when 'query' is not provided")
        sql = f"SELECT {sel} FROM {q.table}"
        return sql

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql}) AS subq"

    # ----- Hash expression -----
    def _token_expr(self, col: str, hashing: HashingCfg) -> str:
        # Normalize NULL and cast to text
        tok = f"COALESCE({col}::text, '{hashing.null_token}')"
        if hashing.case == "lower":
            tok = f"lower({tok})"
        elif hashing.case == "upper":
            tok = f"upper({tok})"
        return tok

    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        cols = list(cols)
        delim = hashing.delimiter.replace(
            "'", "''"
        )  # escape single quotes in SQL literals

        if hashing.algorithm == "double_md5":
            inner_hashes = ", ".join(
                [f"md5({self._token_expr(c, hashing)})" for c in cols]
            )
            return f"lower(md5(concat_ws('{delim}', {inner_hashes})))"

        if hashing.algorithm == "md5_row":
            tokens = ", ".join([self._token_expr(c, hashing) for c in cols])
            return f"lower(md5(concat_ws('{delim}', {tokens})))"

        if hashing.algorithm == "sha256_row":
            # Requires pgcrypto: digest(data, 'sha256') returns bytea, encode(bytea,'hex') returns hex text
            tokens = ", ".join([self._token_expr(c, hashing) for c in cols])
            return f"lower(encode(digest(concat_ws('{delim}', {tokens}), 'sha256'), 'hex'))"

        # Fallback to double_md5 if unknown
        inner_hashes = ", ".join([f"md5({self._token_expr(c, hashing)})" for c in cols])
        return f"lower(md5(concat_ws('{delim}', {inner_hashes})))"

    # ----- Fetch helpers -----
    def fetch_df(self, sql: str) -> pd.DataFrame:
        with self.engine.connect() as c:
            return pd.read_sql(text(sql), c)

    def fetch_scalar(self, sql: str) -> Any:
        with self.engine.connect() as c:
            res = c.execute(text(sql)).scalar()
            return res

    def fetch_column(self, sql: str) -> List[Any]:
        with self.engine.connect() as c:
            res = c.execute(text(sql))
            return [r[0] for r in res.fetchall()]
