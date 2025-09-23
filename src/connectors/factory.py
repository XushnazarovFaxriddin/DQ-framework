"""
Connector factory:
- Detect engine from URI (scheme) or explicit hints if needed
- Instantiate the right connector class from the registry
"""

from urllib.parse import urlparse
from typing import Tuple

from src.runtime.registry import CONNECTORS


def _canonical_engine_from_uri(uri: str) -> str:
    """
    Map a DB URI scheme to our canonical engine key.
    Examples:
      - postgresql+psycopg2://... -> postgres
      - bigquery://project/dataset -> bigquery
      - oracle+oracledb://...      -> oracle
    """
    parsed = urlparse(uri)
    scheme = (parsed.scheme or "").lower()

    # Existing engines
    if scheme.startswith("postgres"):
        return "postgres"
    if scheme.startswith("bigquery"):
        return "bigquery"
    if scheme.startswith("oracle"):
        return "oracle"
    if scheme.startswith("snowflake"):
        return "snowflake"

    # Files & GCS
    if scheme.startswith("file") or scheme.startswith("csv"):
        return "csv"

    if scheme.startswith("gs"):
        path = (parsed.path or "").lower()
        if path.endswith(".parquet") or path.endswith(".pq"):
            return "gcs_parquet"
        if path.endswith(".csv") or path.endswith(".gz") or path.endswith(".csv.gz"):
            return "gcs_csv"
        # default to csv flavor for generic prefixes; caller can override via config if needed
        return "gcs_csv"

    raise ValueError(f"Unsupported or unknown URI scheme: {scheme}")


def build_connector_pair(source_uri: str, target_uri: str):
    """
    Instantiate source and target connectors based on their URIs.
    Returns (source_connector, target_connector, engines_tuple)
    """
    s_eng = _canonical_engine_from_uri(source_uri)
    t_eng = _canonical_engine_from_uri(target_uri)

    if s_eng not in CONNECTORS:
        raise ValueError(f"No registered connector for engine: {s_eng}")
    if t_eng not in CONNECTORS:
        raise ValueError(f"No registered connector for engine: {t_eng}")

    s_cls = CONNECTORS[s_eng]
    t_cls = CONNECTORS[t_eng]

    s = s_cls(source_uri)
    t = t_cls(target_uri)
    return s, t, (s_eng, t_eng)