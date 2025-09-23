"""
BigQuery connector using google-cloud-bigquery.

Hashing notes:
- We normalize values via COALESCE(CAST(col AS STRING), '<null_token>').
- Case folding is applied via LOWER()/UPPER() when requested.
- Algorithms:
  * double_md5 (default): LOWER(TO_HEX(MD5(TO_BYTES(CONCAT(h1,'|',h2,...)))))
    where hi = LOWER(TO_HEX(MD5(TO_BYTES(token_i))))
  * md5_row: LOWER(TO_HEX(MD5(TO_BYTES(CONCAT(token1,'|',token2,...)))))
  * sha256_row: LOWER(TO_HEX(SHA256(TO_BYTES(CONCAT(token1,'|',token2,...)))))
- LOWER(...) is applied to the final HEX to match Postgres' lowercase md5 output.
"""

from typing import Iterable, List, Optional, Any
import pandas as pd
from google.cloud import bigquery

from src.connectors.base import BaseConnector
from src.runtime.registry import register_connector
from src.compiler.schema import QueryCfg, HashingCfg


@register_connector("bigquery")
class BigQueryConnector(BaseConnector):
    engine_name = "bigquery"

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        self.client = bigquery.Client()

    # ----- SQL rendering -----
    def render_select_sql(self, q: QueryCfg, *, columns: Optional[List[str]] = None) -> str:
        if q.query:
            return q.query
        sel = q.select.strip() if q.select else "*"
        if columns and not q.select:
            sel = ", ".join(columns)
        if not q.table:
            raise ValueError("QueryCfg requires 'table' when 'query' is not provided")
        return f"SELECT {sel} FROM `{q.table}`"

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql})"

    # ----- Hash expression -----
    def _token_expr(self, col: str, hashing: HashingCfg) -> str:
        tok = f"COALESCE(CAST({col} AS STRING), '{hashing.null_token}')"
        if hashing.case == "lower":
            tok = f"LOWER({tok})"
        elif hashing.case == "upper":
            tok = f"UPPER({tok})"
        return tok

    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        cols = list(cols)
        delim = hashing.delimiter.replace("'", r"\'")  # escape single quotes

        def md5_hex(s: str) -> str:
            # MD5 requires BYTES; TO_HEX returns uppercase HEX; we LOWER it for consistency.
            return f"LOWER(TO_HEX(MD5(TO_BYTES({s}))))"

        def sha256_hex(s: str) -> str:
            return f"LOWER(TO_HEX(SHA256(TO_BYTES({s}))))"

        if hashing.algorithm == "double_md5":
            inner = []
            for c in cols:
                tok = self._token_expr(c, hashing)
                inner.append(md5_hex(tok))
            concat_args = []
            for i, e in enumerate(inner):
                if i > 0:
                    concat_args.append(f"'{delim}'")
                concat_args.append(e)
            chain = "CONCAT(" + ", ".join(concat_args) + ")"
            return md5_hex(chain)

        if hashing.algorithm == "md5_row":
            tokens = []
            for i, c in enumerate(cols):
                tok = self._token_expr(c, hashing)
                if i > 0:
                    tokens.append(f"'{delim}'")
                tokens.append(tok)
            chain = "CONCAT(" + ", ".join(tokens) + ")"
            return md5_hex(chain)

        if hashing.algorithm == "sha256_row":
            tokens = []
            for i, c in enumerate(cols):
                tok = self._token_expr(c, hashing)
                if i > 0:
                    tokens.append(f"'{delim}'")
                tokens.append(tok)
            chain = "CONCAT(" + ", ".join(tokens) + ")"
            return sha256_hex(chain)

        # Fallback to double_md5
        inner = []
        for c in cols:
            tok = self._token_expr(c, hashing)
            inner.append(md5_hex(tok))
        concat_args = []
        for i, e in enumerate(inner):
            if i > 0:
                concat_args.append(f"'{delim}'")
            concat_args.append(e)
        chain = "CONCAT(" + ", ".join(concat_args) + ")"
        return md5_hex(chain)

    # ----- Fetch helpers -----
    def fetch_df(self, sql: str) -> pd.DataFrame:
        return self.client.query(sql).to_dataframe()

    def fetch_scalar(self, sql: str) -> Any:
        rows = list(self.client.query(sql))
        if not rows:
            return None
        return rows[0][0]

    def fetch_column(self, sql: str) -> List[Any]:
        rows = list(self.client.query(sql))
        return [r[0] for r in rows]
