"""Persistent storage helpers for table statistics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from google.cloud import bigquery

from src.compiler.schema import TableStatsStorageCfg


class StatsStorageBackend(ABC):
    def __init__(self, table: str) -> None:
        self._table = table

    @property
    def table(self) -> str:
        return self._table

    @abstractmethod
    def persist(self, rows: List[Dict[str, Any]]) -> None:
        ...


class BigQueryStatsStorage(StatsStorageBackend):
    def __init__(self, table: str, *, project: Optional[str] = None) -> None:
        super().__init__(table)
        self._client = bigquery.Client(project=project)
        self._table_ref = bigquery.TableReference.from_string(table, default_project=project)

    def persist(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        errors = self._client.insert_rows_json(self._table_ref, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert errors: {errors}")


def build_stats_storage(cfg: TableStatsStorageCfg) -> StatsStorageBackend:
    if cfg.backend == "bigquery":
        return BigQueryStatsStorage(table=cfg.table, project=cfg.project)
    raise ValueError(f"Unsupported stats storage backend: {cfg.backend}")
