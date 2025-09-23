"""
GCS Parquet connector powered by DuckDB SQL.

Capabilities:
- Native SQL via read_parquet('gs://bucket/path...') with httpfs+parquet extensions
- Column projection and filters are pushed down when possible
- Hashing policy: supports "double_md5" and "md5_row" (sha256_row not supported here)

Auth:
- Relies on environment/ADC that DuckDB's httpfs can use. Ensure required env/credentials are available in runtime.

Notes:
- QueryCfg.table must be a gs:// path, either a single file or a glob/prefix supported by DuckDB.
- QueryCfg.query can be used to pass a custom SQL with read_parquet('gs://...').
"""

from typing import Iterable, List, Optional, Any
import hashlib
import duckdb
import pandas as pd

from src.connectors.base import BaseConnector
from src.compiler.schema import QueryCfg, HashingCfg
from src.runtime.registry import register_connector


@register_connector("gcs_parquet")
class GcsParquetConnector(BaseConnector):
    engine_name = "gcs_parquet"

    def __init__(self, uri: str) -> None:
        """
        uri example: gcs+parquet://  (scheme is informational for factory)
        The actual GCS path comes from QueryCfg.table.
        """
        super().__init__(uri)
        self.con = duckdb.connect(database=":memory:")
        self._ensure_extensions()

    def _ensure_extensions(self) -> None:
        def _register_digest(conn):
            def _md5(value: Any) -> str:
                data = "" if value is None else str(value)
                return hashlib.md5(data.encode("utf-8")).hexdigest()

            conn.create_function("md5", _md5, return_type=str)

        for name, required in (
            ("httpfs", True),
            ("parquet", True),
            ("json", False),
            ("digest", True),
        ):
            try:
                self.con.execute(f"INSTALL {name};")
            except Exception:
                if required:
                    if name == "digest":
                        _register_digest(self.con)
                        continue
                    raise
            try:
                self.con.execute(f"LOAD {name};")
            except Exception:
                if required:
                    if name == "digest":
                        _register_digest(self.con)
                        continue
                    raise

    def _base_from_parquet(self, gspath: str) -> str:
        return f"read_parquet('{gspath}')"

    def render_select_sql(
        self, q: QueryCfg, *, columns: Optional[List[str]] = None
    ) -> str:
        if q.query:
            return q.query
        if not q.table:
            raise ValueError(
                "GCS Parquet connector requires QueryCfg.table to be a gs:// path"
            )
        src = self._base_from_parquet(q.table)
        sel = "*"
        if q.select and not columns:
            sel = q.select
        elif columns and not q.select:
            sel = ", ".join(columns)
        return f"SELECT {sel} FROM {src}"

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql})"

    # Hash expression (md5-based)
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
            pieces = []
            for i, c in enumerate(cols):
                if i > 0:
                    pieces.append(f"'{delim}'")
                pieces.append(f"md5({self._token(c, hashing)})")
            chain = "concat(" + ", ".join(pieces) + ")"
            return f"lower(md5({chain}))"

        if hashing.algorithm == "md5_row":
            pieces = []
            for i, c in enumerate(cols):
                if i > 0:
                    pieces.append(f"'{delim}'")
                pieces.append(self._token(c, hashing))
            chain = "concat(" + ", ".join(pieces) + ")"
            return f"lower(md5({chain}))"

        raise NotImplementedError(
            "gcs_parquet supports only double_md5 and md5_row algorithms"
        )

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
