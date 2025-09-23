"""Factory helpers to instantiate connectors from URIs."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from src.runtime.registry import CONNECTORS


_SCHEME_ALIASES = {
    "postgres": "postgres",
    "postgresql": "postgres",
    "postgresql+psycopg2": "postgres",
    "pg": "postgres",
    "bigquery": "bigquery",
    "bq": "bigquery",
    "oracle": "oracle",
    "oracle+oracledb": "oracle",
    "snowflake": "snowflake",
    "snowflake+connector": "snowflake",
    "csv": "csv",
    "file": "csv",
    "duckdb": "csv",
    "rest": "rest_api",
    "rest_api": "rest_api",
    "airtable": "airtable",
}


def _infer_gcs_engine(path: str, declared: Optional[str]) -> str:
    if declared in {"gcs_parquet", "gcs_csv"}:
        return declared
    lower_path = path.lower()
    if lower_path.endswith((".parquet", ".pq")):
        return "gcs_parquet"
    if lower_path.endswith((".csv", ".csv.gz", ".gz")):
        return "gcs_csv"
    return "gcs_csv"


def _canonical_engine_from_uri(uri: str, declared: Optional[str] = None) -> str:
    if declared:
        return declared

    parsed = urlparse(uri)
    scheme = (parsed.scheme or "").lower()

    if scheme in {"gs", "gcs", "gcs+parquet", "gcs+csv"}:
        return _infer_gcs_engine(
            parsed.path or "", None if declared is None else declared
        )

    if "+" in scheme:
        base, _sep, _driver = scheme.partition("+")
        scheme = base

    if scheme in _SCHEME_ALIASES:
        return _SCHEME_ALIASES[scheme]

    if not scheme and uri.lower().endswith((".csv", ".csv.gz")):
        return "csv"

    raise ValueError(f"Unsupported or unknown URI scheme: {scheme}")


def build_connector(uri: str, declared_engine: Optional[str] = None):
    engine = _canonical_engine_from_uri(uri, declared_engine)
    if engine not in CONNECTORS:
        raise ValueError(f"No registered connector for engine '{engine}'")
    connector_cls = CONNECTORS[engine]
    connector = connector_cls(uri)
    return connector, engine


def build_connector_pair(
    source_uri: str,
    target_uri: str,
    *,
    source_declared: Optional[str] = None,
    target_declared: Optional[str] = None,
):
    source, source_engine = build_connector(source_uri, source_declared)
    target, target_engine = build_connector(target_uri, target_declared)
    return source, target, (source_engine, target_engine)
