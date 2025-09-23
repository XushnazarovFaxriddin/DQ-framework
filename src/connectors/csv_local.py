"""
CSV (local filesystem) connector powered by DuckDB SQL.

Capabilities:
- Native SQL via DuckDB around read_csv_auto(<path>)
- Column projection is handled in SQL layer
- Row count / column extraction supported
- Hashing policy: supports "double_md5" and "md5_row" via DuckDB digest extension
  (sha256_row is not supported here to preserve deterministic hex outputs across engines)

Notes:
- This connector expects QueryCfg.table to be a filesystem path to a CSV file.
- QueryCfg.query can be used for custom SQL; in that case the query must reference read_csv_auto('<path>')
  or be a fully independent SQL statement.
"""

from typing import Iterable, List, Optional, Any
import hashlib
import os
import duckdb
import pandas as pd

from src.connectors.base import BaseConnector
from src.compiler.schema import QueryCfg, HashingCfg
from src.runtime.registry import register_connector


@register_connector("csv")
class CsvLocalConnector(BaseConnector):
    engine_name = "csv"

    def __init__(self, uri: str) -> None:
        """
        uri example: csv:// (scheme is informational for factory)
        The actual CSV path comes from QueryCfg.table.
        """
        super().__init__(uri)
        self.con = duckdb.connect(database=":memory:")
        self._ensure_extensions()

    # ------------------------------
    # DuckDB extension bootstrap
    # ------------------------------
    def _register_digest_udf(self) -> None:
        def _md5(value: Any) -> str:
            data = "" if value is None else str(value)
            return hashlib.md5(data.encode("utf-8")).hexdigest()

        self.con.create_function("md5", _md5, return_type=str)

    def _try_install(self, name: str, *, required: bool = False) -> None:
        try:
            self.con.execute(f"INSTALL {name};")
        except Exception:
            if required:
                if name == "digest":
                    self._register_digest_udf()
                    return
                raise
        try:
            self.con.execute(f"LOAD {name};")
        except Exception:
            if required:
                if name == "digest":
                    self._register_digest_udf()
                    return
                raise

    def _ensure_extensions(self) -> None:
        self._try_install("httpfs")
        self._try_install("parquet")
        self._try_install("json")
        self._try_install("digest", required=True)

    # ------------------------------
    # SQL rendering
    # ------------------------------
    def _base_from_csv(self, path: str) -> str:
        # Always build a direct table function reference; avoids stateful VIEWs
        abspath = os.path.abspath(path)
        return f"read_csv_auto('{abspath}', AUTO_DETECT=TRUE, HEADER=TRUE)"

    def render_select_sql(
        self, q: QueryCfg, *, columns: Optional[List[str]] = None
    ) -> str:
        if q.query:
            # Trust user-provided SQL verbatim
            return q.query

        if not q.table:
            raise ValueError(
                "CSV connector requires QueryCfg.table to be a CSV file path"
            )

        src = self._base_from_csv(q.table)
        sel = "*"
        if q.select and not columns:
            sel = q.select
        elif columns and not q.select:
            sel = ", ".join(columns)

        return f"SELECT {sel} FROM {src}"

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql})"

    # ------------------------------
    # Hash expression (DuckDB dialect)
    # ------------------------------
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
            # concat_ws equivalent: concat with delimiters interleaved
            pieces = []
            for i, e in enumerate(cols):
                if i > 0:
                    pieces.append(f"'{delim}'")
                pieces.append(f"md5({self._token(e, hashing)})")
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
            "csv connector supports only double_md5 and md5_row algorithms"
        )

    # ------------------------------
    # Fetch helpers
    # ------------------------------
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
