"""
BaseConnector defines the minimal API each connector must implement.
"""

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional, Any
import pandas as pd

from src.compiler.schema import QueryCfg, HashingCfg


class BaseConnector(ABC):
    engine_name: str = "base"

    def __init__(self, uri: str) -> None:
        self.uri = uri

    # ---- SQL rendering helpers ----
    @abstractmethod
    def render_select_sql(self, q: QueryCfg, *, columns: Optional[List[str]] = None) -> str:
        """
        Render a SELECT statement based on:
          - q.query  (native SQL)   -> return as-is (wrapped if needed)
          - q.table  (+ optional select) -> SELECT <select|*> FROM <table>
        Optionally force a column subset via 'columns'.
        """
        ...

    @abstractmethod
    def render_count_sql(self, inner_sql: str) -> str:
        """Wrap inner_sql into SELECT COUNT(*) according to dialect."""
        ...

    @abstractmethod
    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        """
        Return a dialect-specific canonical hash expression over given columns
        following the requested hashing policy.
        The output MUST be comparable across engines (same hex-case, same semantics).
        """
        ...

    # ---- Data fetch helpers ----
    @abstractmethod
    def fetch_df(self, sql: str) -> pd.DataFrame: ...

    @abstractmethod
    def fetch_scalar(self, sql: str) -> Any: ...

    @abstractmethod
    def fetch_column(self, sql: str) -> List[Any]: ...
