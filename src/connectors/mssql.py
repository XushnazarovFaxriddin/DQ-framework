"""
MSSQL (SQL Server) connector using pymssql.

Notes:
- No ODBC driver required, works inside Docker with just `pymssql`.
- Hashing:
  * double_md5: simulate by nested MD5 calls
  * md5_row: MD5 of concatenated row tokens
  * sha256_row: use HASHBYTES('SHA2_256', ...)
- Output: lowercase hex string
"""

from typing import Iterable, List, Optional, Any
import pandas as pd
import pymssql

from src.connectors.base import BaseConnector
from src.runtime.registry import register_connector
from src.compiler.schema import QueryCfg, HashingCfg


@register_connector("mssql")
class MSSQLConnector(BaseConnector):
    engine_name = "mssql"

    def __init__(self, uri: str) -> None:
        """
        URI format (custom, parsed manually):
        mssql://user:password@host:port/database
        """
        super().__init__(uri)
        self.conn_params = self._parse_uri(uri)

    def _parse_uri(self, uri: str) -> dict:
        # Example: mssql://sa:Passw0rd@localhost:1433/mydb
        if not uri.startswith("mssql://"):
            raise ValueError("MSSQL URI must start with mssql://")

        raw = uri[len("mssql://") :]
        auth, rest = raw.split("@", 1)
        user, pwd = auth.split(":", 1)
        hostport, db = rest.split("/", 1)
        if ":" in hostport:
            host, port = hostport.split(":")
        else:
            host, port = hostport, "1433"

        return {
            "server": host,
            "port": int(port),
            "user": user,
            "password": pwd,
            "database": db,
        }

    def _connect(self):
        return pymssql.connect(**self.conn_params)

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
        return f"SELECT {sel} FROM {q.table}"

    def render_count_sql(self, inner_sql: str) -> str:
        return f"SELECT COUNT(*) AS c FROM ({inner_sql}) AS subq"

    # ----- Hash expression -----
    def _token_expr(self, col: str, hashing: HashingCfg) -> str:
        tok = f"ISNULL(CAST({col} AS NVARCHAR(MAX)), '{hashing.null_token}')"
        if hashing.case == "lower":
            tok = f"LOWER({tok})"
        elif hashing.case == "upper":
            tok = f"UPPER({tok})"
        return tok

    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        cols = list(cols)
        delim = hashing.delimiter.replace("'", "''")
        tokens = " + '{delim}' + ".format(delim=delim).join(
            [self._token_expr(c, hashing) for c in cols]
        )

        if hashing.algorithm == "double_md5":
            inner = " + '{delim}' + ".format(delim=delim).join(
                [f"CONVERT(VARCHAR(32), HASHBYTES('MD5', {self._token_expr(c, hashing)}), 2)" for c in cols]
            )
            return f"LOWER(CONVERT(VARCHAR(32), HASHBYTES('MD5', {inner}), 2))"

        if hashing.algorithm == "md5_row":
            return f"LOWER(CONVERT(VARCHAR(32), HASHBYTES('MD5', {tokens}), 2))"

        if hashing.algorithm == "sha256_row":
            return f"LOWER(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', {tokens}), 2))"

        # fallback
        inner = " + '{delim}' + ".format(delim=delim).join(
            [f"CONVERT(VARCHAR(32), HASHBYTES('MD5', {self._token_expr(c, hashing)}), 2)" for c in cols]
        )
        return f"LOWER(CONVERT(VARCHAR(32), HASHBYTES('MD5', {inner}), 2))"

    # ----- Fetch helpers -----
    def fetch_df(self, sql: str) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql(sql, conn)

    def fetch_scalar(self, sql: str) -> Any:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql)
            row = cur.fetchone()
            return row[0] if row else None

    def fetch_column(self, sql: str) -> List[Any]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]

    # ----- Information schema -----
    def information_schema_columns(self, table_name: str) -> List[dict]:
        sql = f"""
        SELECT column_name, data_type, is_nullable
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE table_name = '{table_name.split('.')[-1]}'
        """
        with self._connect() as conn:
            cur = conn.cursor(as_dict=True)
            cur.execute(sql)
            return list(cur.fetchall())
