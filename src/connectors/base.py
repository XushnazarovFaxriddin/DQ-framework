"""Base interface for all connectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from src.compiler.schema import HashingCfg, QueryCfg


class BaseConnector(ABC):
    """Abstract base class for all connectors."""

    engine_name: str = "base"

    def __init__(self, uri: str) -> None:
        self.uri = uri

    @abstractmethod
    def render_select_sql(
        self, q: QueryCfg, *, columns: Optional[List[str]] = None
    ) -> str:
        """Render a ``SELECT`` statement for the provided :class:`QueryCfg`."""

    @abstractmethod
    def render_count_sql(self, inner_sql: str) -> str:
        """Wrap ``inner_sql`` into a dialect specific ``SELECT COUNT(*)``."""

    @abstractmethod
    def hash_expr(self, cols: Iterable[str], hashing: HashingCfg) -> str:
        """Return a deterministic hash expression over ``cols``."""

    @abstractmethod
    def fetch_df(self, sql: str) -> pd.DataFrame:
        """Return a :class:`pandas.DataFrame` for ``sql``."""

    @abstractmethod
    def fetch_scalar(self, sql: str) -> Any:
        """Return a scalar value for ``sql``."""

    @abstractmethod
    def fetch_column(self, sql: str) -> List[Any]:
        """Return the first column from ``sql`` as a list."""

    def information_schema_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Return information schema metadata when supported."""

        raise NotImplementedError(
            f"information_schema_columns not implemented for {self.engine_name}"
        )
