"""
GCS CSV connector powered by DuckDB SQL.

Capabilities:
- Native SQL via read_csv_auto('gs://bucket/path...') with httpfs extension
- Column projection is handled in SQL
- Hashing policy: supports "double_md5" and "md5_row" (sha256_row not supported)

Notes:
- QueryCfg.table must be a gs:// path (single file or glob/prefix).
- Ensure DuckDB httpfs can authenticate to GCS in your environment.
"""

from typing import Iterable, List, Optional, Any
import duckdb
import pandas as pd

from src.connectors.base import BaseConnector
from src.compiler.schema import QueryCfg, HashingCfg
from src.runtime.registry import register_connector


@register_connector("gcs_csv")
class GcsCsvConnector(BaseConnector):
    engine_name = "gcs_csv"

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        self.con = duckdb.connect(database=":memory:")
        self._ensure_extensions()

    def _ensure_extensions(self) -> None:
        self.con.execute("INSTALL httpfs; LOAD httpfs;")
        self.con.execute("INSTALL parquet; LOAD parquet;")  # not strictly needed, but harmless
        self.con.execute("INSTALL json; LOAD json;")
        self.con.execute("INSTALL digest; LOAD digest;")

    def _base_from_csv(self, gspath: str) -> str:
        return f"read_csv_auto('{gspath}', AUTO_DETECT=TRUE, HEADER=TRUE)"

    def render_select_sql(self, q: QueryCfg, *, columns: Optional[List[str]] = None) -> str:
        if q.query:
            return q.query
        if not q.table:
            raise ValueError("GCS CSV connector requires QueryCfg.table to be a gs:// path")
        src = self._base_from_csv(q.table)
        sel = "*"
        if q.select and not columns:
            sel = q.select
        elif columns and not q.select:
            sel = ", ".join(columns)
        return f"SELECT {sel} FROM {src}"

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql})"

    def _token(self, col: str, hashing: HashingCfg) -> str:
        tok = f"COALESCE(CAST({col} AS VARCHAR), '{hashing.null_token}')"
        if hashing.case == "lower":
            tok = f"lower({tok})"
        elif hashing.case == "upper":
            tok = f"upper({tok})"
        return tok

    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        cols = list(cols)
        delim = hashing.delimiter.replace("'", "''")

        if hashing.algorithm == "double_md5":
            parts = []
            for i, c in enumerate(cols):
                if i > 0:
                    parts.append(f"'{delim}'")
                parts.append(f"md5({self._token(c, hashing)})")
            chain = "concat(" + ", ".join(parts) + ")"
            return f"lower(md5({chain}))"

        if hashing.algorithm == "md5_row":
            parts = []
            for i, c in enumerate(cols):
                if i > 0:
                    parts.append(f"'{delim}'")
                parts.append(self._token(c, hashing))
            chain = "concat(" + ", ".join(parts) + ")"
            return f"lower(md5({chain}))"

        raise NotImplementedError("gcs_csv supports only double_md5 and md5_row algorithms")

    def fetch_df(self, sql: str) -> pd.DataFrame:
        return self.con.execute(sql).df()

    def fetch_scalar(self, sql: str) -> Any:
        res = self.con.execute(sql).fetchone()
        return res[0] if res else None

    def fetch_column(self, sql: str) -> List[Any]:
        df = self.con.execute(sql).df()
        if df.shape[1] != 1:
            raise ValueError("fetch_column expects exactly one selected column")
        return df.iloc[:, 0].tolist()
