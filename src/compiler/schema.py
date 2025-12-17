from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _env_int(var_name: str, default: int) -> int:
    val = os.getenv(var_name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _default_chunk_size() -> int:
    return _env_int("DQF_DEFAULT_MISMATCH_CHUNK_SIZE", 1_000_000)


def _default_max_ranges() -> int:
    return _env_int("DQF_DEFAULT_MISMATCH_MAX_RANGES", 5)


def _default_max_scan_chunks() -> int:
    return _env_int("DQF_DEFAULT_MISMATCH_MAX_SCAN_CHUNKS", 100)


def _default_binary_depth() -> int:
    return _env_int("DQF_DEFAULT_MISMATCH_BINARY_DEPTH", 5)


def _env_str(var_name: str, default: Optional[str]) -> Optional[str]:
    val = os.getenv(var_name)
    if val is None or val == "":
        return default
    return val


def _default_results_backend() -> str:
    return _env_str("DQF_RESULTS_BACKEND", "local") or "local"


def _default_results_bucket() -> Optional[str]:
    return _env_str("DQF_RESULTS_BUCKET", None)


def _default_results_base_path() -> str:
    return _env_str("DQF_RESULTS_BASE_PATH", "mismatch_ranges") or "mismatch_ranges"


def _default_results_public_url_prefix() -> Optional[str]:
    return _env_str("DQF_RESULTS_PUBLIC_URL_PREFIX", None)


def _default_mismatch_ids_chunk_size() -> int:
    return _env_int("DQF_MISMATCH_IDS_CHUNK_SIZE", 500_000)


def _default_mismatch_ids_max_ids() -> int:
    return _env_int("DQF_MISMATCH_IDS_MAX_IDS", 100_000)


def _default_mismatch_ids_enabled() -> bool:
    val = os.getenv("DQF_MISMATCH_IDS_ENABLED", "true")
    return val.lower() in ("true", "1", "yes")


class HashingCfg(BaseModel):
    """
    Hashing policy for cross-engine consistency.
    algorithm:
      - "double_md5" (default): md5(md5(col1)||'|'||md5(col2)||'|...')
      - "md5_row": md5(CONCAT(norm(col1), SEP, norm(col2), ...))
      - "sha256_row": sha256(CONCAT(norm(col1), SEP, norm(col2), ...))  # requires engine support
    null_token: replacement for NULL before hashing
    delimiter: delimiter between tokens when concatenating
    case: value normalization before hashing: "none" | "lower" | "upper"
    """

    algorithm: str = "double_md5"
    null_token: str = ""
    delimiter: str = "|"
    case: str = "upper"  # none|lower|upper

    @field_validator("algorithm")
    @classmethod
    def _validate_algorithm(cls, value: str) -> str:
        allowed = {"double_md5", "md5_row", "sha256_row"}
        if value not in allowed:
            raise ValueError(f"Unsupported hashing algorithm: {value}")
        return value

    @field_validator("case")
    @classmethod
    def _validate_case(cls, value: str) -> str:
        allowed = {"none", "lower", "upper"}
        if value not in allowed:
            raise ValueError(f"Hashing case must be one of {allowed}")
        return value


class ConnectionsCfg(BaseModel):
    """
    Connection configuration:
    - *_env_var: where to read the URI from (e.g., env var name)
    - *_type: optional declared engine type for validation/telemetry (e.g., "postgres", "bigquery", "gcs_parquet")
    """

    source_env_var: str
    target_env_var: str
    source_type: Optional[str] = None
    target_type: Optional[str] = None


class QueryCfg(BaseModel):
    """
    Source/Target query definition.
    Exactly one of `table`, `select`, or `query` may be provided OR reasonable combinations:
      - table alone => SELECT * FROM table
      - table + select => SELECT <select> FROM table
      - query alone => use as-is (native SQL)
    Optional fields:
      - order_by: used to impose a deterministic ordering before hashing/joins when needed
      - filters: config-level hints (can be rendered by planners or templates if desired)
    """

    table: Optional[str] = None
    select: Optional[str] = None
    query: Optional[str] = None
    order_by: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None

    @field_validator("query")
    @classmethod
    def _strip_query(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v


class ColumnMapEntry(BaseModel):
    """
    Canonical column mapping.
    'source' and 'target' may be plain column names or SQL expressions understood by each side.
    Example:
      api_id:
        source: api_id
        target: ApiId
      amount:
        source: amount
        target: total_amount
    """

    source: str
    target: str


class MismatchSamplingCfg(BaseModel):
    mode: Literal["chunk", "binary"]
    chunk_size: Optional[int] = Field(default_factory=_default_chunk_size)
    max_ranges: int = Field(default_factory=_default_max_ranges)
    max_scan_chunks: int = Field(default_factory=_default_max_scan_chunks)
    max_depth: int = Field(default_factory=_default_binary_depth)
    range_start: Optional[int] = None
    range_end: Optional[int] = None


class MismatchCsvCfg(BaseModel):
    enabled: bool = False
    backend: Literal["local", "gcs"] = Field(default_factory=_default_results_backend)
    bucket: Optional[str] = Field(default_factory=_default_results_bucket)
    base_path: str = Field(default_factory=_default_results_base_path)
    public_url_prefix: Optional[str] = Field(
        default_factory=_default_results_public_url_prefix
    )
    # Path template for mismatch IDs CSV files
    # Supports: {config_file}, {check_name}, {table_name}, {date}, {timestamp}
    # Example: "{config_file}/{check_name}/{table_name}-{date}.csv"
    path_template: Optional[str] = None


class MismatchIdsCfg(BaseModel):
    """
    Configuration for mismatch IDs detection and export.

    When row_count/aggregations[count]/aggregations[distinct_count] checks fail,
    this enables finding and exporting the actual mismatched IDs to GCS/local storage.

    Features:
    - Detects IDs present in source but missing in target (missing_in_target)
    - Detects IDs present in target but missing in source (extra_in_target) - CRITICAL
    - Exports to CSV with dashboard-ready metadata
    - Optimized for 10M+ rows using chunked/binary algorithms

    Path template variables:
    - {config_file}: Name of the config file (e.g., "sw_selected_validation")
    - {check_name}: Type of check (e.g., "row_count", "aggregations")
    - {table_name}: Name of the table being validated
    - {date}: Date in YYYYMMDD_HHMMSS format (EST timezone)
    - {timestamp}: Unix timestamp

    Example path_template: "{config_file}/{check_name}/{table_name}-{date}.csv"
    """

    enabled: bool = Field(default_factory=_default_mismatch_ids_enabled)
    backend: Literal["local", "gcs"] = Field(default_factory=_default_results_backend)
    bucket: Optional[str] = Field(default_factory=_default_results_bucket)
    base_path: str = Field(default_factory=_default_results_base_path)
    public_url_prefix: Optional[str] = Field(
        default_factory=_default_results_public_url_prefix
    )
    # Path template for CSV files
    path_template: str = "{config_file}/{check_name}/{table_name}-{date}.csv"
    # Maximum IDs to export per mismatch type
    max_ids: int = Field(default_factory=_default_mismatch_ids_max_ids)
    # Chunk size for ID fetching (memory efficiency)
    chunk_size: int = Field(default_factory=_default_mismatch_ids_chunk_size)
    # Export separate CSVs for missing_in_target and extra_in_target
    separate_files: bool = False


class SeverityRuleCfg(BaseModel):
    condition: Optional[str] = None
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    older_than_days: Optional[int] = None
    newer_than_days: Optional[int] = None
    tolerance_pct_exceeded_gte: Optional[float] = None
    tolerance_pct_exceeded_lt: Optional[float] = None
    tolerance_abs_exceeded_gte: Optional[float] = None
    tolerance_abs_exceeded_lt: Optional[float] = None
    reason: Optional[str] = None

    @model_validator(mode="after")
    def _ensure_severity(cls, values: "SeverityRuleCfg") -> "SeverityRuleCfg":
        if values.severity not in ("INFO", "WARNING", "CRITICAL"):
            raise ValueError("severity must be INFO, WARNING, or CRITICAL")
        return values


class TableStatsMetricCfg(BaseModel):
    method: str
    column: Optional[str] = None
    name: Optional[str] = None


class AdaptiveThresholdCfg(BaseModel):
    when: Literal["last_hours", "older_than_days"]
    hours: Optional[int] = None
    days: Optional[int] = None
    tolerance_pct: Optional[float] = None
    tolerance_abs: Optional[float] = None

    @model_validator(mode="after")
    def _ensure_args(cls, values: "AdaptiveThresholdCfg") -> "AdaptiveThresholdCfg":
        if values.tolerance_pct is None and values.tolerance_abs is None:
            raise ValueError("adaptive_threshold requires tolerance_pct or tolerance_abs")
        if values.when == "last_hours" and (values.hours is None or values.hours <= 0):
            raise ValueError("last_hours adaptive threshold requires positive 'hours'")
        if values.when == "older_than_days" and (values.days is None or values.days <= 0):
            raise ValueError("older_than_days adaptive threshold requires positive 'days'")
        return values


class StatsCompareWindowCfg(BaseModel):
    period_granularity: Literal["day", "week", "month", "year"]
    lookback_days: Optional[int] = None
    lookback_weeks: Optional[int] = None
    lookback_months: Optional[int] = None
    lookback_years: Optional[int] = None


class TableStatsStorageCfg(BaseModel):
    backend: Literal["bigquery"] = "bigquery"
    table: str
    project: Optional[str] = None


class CheckCfg(BaseModel):
    """
    Generic check configuration with multiple ways to define compared columns:
    - include_map: { canonical: {source: "...", target: "..."} }  # highest priority
    - include + table-level column_map                           # common path
    - include_source + include_target (pairwise, same length)    # fallback
    - include only (assume identical names on both sides)         # simple case
    Column selection priority remains the same (include_map > table.column_map+include > include_source/target > include).
    Ordering:
      - order_by: canonical columns (applies when aligned projections are used)
      - order_by_source: raw SQL expressions for source side
      - order_by_target: raw SQL expressions for target side
    Note: Ordering primarily affects preview/sampling (e.g., join_rowdiff LIMIT) and deterministic outputs.
    """

    type: str

    # Column selection/mapping
    include: Optional[List[str]] = None
    include_source: Optional[List[str]] = None
    include_target: Optional[List[str]] = None
    include_map: Optional[Dict[str, ColumnMapEntry]] = None

    exclude: Optional[List[str]] = None
    rules: Optional[List[Dict[str, Any]]] = None
    column: Optional[str] = None  # e.g., for freshness
    col: Optional[str] = None  # alias for 'column'
    id_column: Optional[str] = None
    id_column_source: Optional[str] = None
    id_column_target: Optional[str] = None
    on: Optional[str] = None # source|target
    max_lag_minutes: Optional[int] = None
    tolerance_pct: Optional[float] = None
    tolerance_abs: Optional[float] = None
    join_keys: Optional[Dict[str, List[str]]] = None
    logic: Optional[Any] = None  # Python configs only

    allowed_values: Optional[List[Any]] = None
    include_values: Optional[List[Any]] = None
    exclude_values: Optional[List[Any]] = None
    regex: Optional[str] = None
    min: Optional[int] = None
    max: Optional[int] = None

    mode: Optional[str] = None # single|dual
    sql_source: Optional[str] = None
    sql_target: Optional[str] = None
    sql: Optional[str] = None
    expected_result: Optional[Any] = None
    compare_mode: Optional[str] = None # equals|less|greater
    tolerance_time_sec: Optional[int] = None
    tolerance_time_min: Optional[int] =  None

    time_column: Optional[str] = None
    time_column_source: Optional[str] = None
    time_column_target: Optional[str] = None
    time_granularity: Optional[str] = None
    metrics: Optional[List[TableStatsMetricCfg]] = None
    stats_storage: Optional[TableStatsStorageCfg] = None

    stats_table: Optional[str] = None
    stats_table_side: Optional[str] = None
    table_name: Optional[str] = None
    compare_on: Optional[List[StatsCompareWindowCfg]] = None
    severity_rules: Optional[List[SeverityRuleCfg]] = None

    # ordering
    order_by: Optional[List[str]] = None  # canonical column names (after alignment)
    mismatch_sampling: Optional[MismatchSamplingCfg] = None
    order_by_source: Optional[List[str]] = None  # raw SQL expressions for source side
    order_by_target: Optional[List[str]] = None  # raw SQL expressions for target side


class TableCfg(BaseModel):
    """
    Per-table config with optional canonical column mapping.
    - dynamic_pattern=True enables wildcard-based expansion handled by the planner.
    - 'column_map' defines canonical columns available for alignment.
    """

    name: str
    dynamic_pattern: Optional[bool] = False
    source: QueryCfg
    target: QueryCfg
    column_map: Optional[Dict[str, ColumnMapEntry]] = None
    checks: List[CheckCfg]


class DefaultsCfg(BaseModel):
    row_limit: int = 1000
    thresholds: Dict[str, float] = Field(default_factory=dict)
    hashing: HashingCfg = HashingCfg()


class AlertsCfg(BaseModel):
    """
    Example:
      routes:
        - kind: gchat                 # GChat always uses env webhook
          mode: card                  # or text
        - kind: email
          to: ["jamshid.allayev@virginvoyages.com"]      # if omitted, fallback to env DQ_EMAILS
    """

    routes: List[Dict[str, Any]] = Field(default_factory=list)


class PlanningCfg(BaseModel):
    """
    Optional planning hints (e.g., partitioning strategy).
    """

    partitions: Optional[Dict[str, Any]] = None


class ResultsTableCfg(BaseModel):
    enabled: bool = False
    backend: Literal["bigquery"] = "bigquery"
    table: Optional[str] = None
    project: Optional[str] = None


class ResultsStorageCfg(BaseModel):
    mismatch_csv: Optional[MismatchCsvCfg] = None
    mismatch_ids: Optional[MismatchIdsCfg] = None
    runs: Optional[ResultsTableCfg] = None
    checks: Optional[ResultsTableCfg] = None


class ConfigModel(BaseModel):
    """
    Top-level config schema.
    """

    connections: ConnectionsCfg
    defaults: Optional[DefaultsCfg] = DefaultsCfg()
    tables: List[TableCfg]
    results_storage: Optional[ResultsStorageCfg] = None
    planning: Optional[PlanningCfg] = None
    alerts: Optional[AlertsCfg] = AlertsCfg()
