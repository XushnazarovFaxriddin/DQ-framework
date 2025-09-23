from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

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
    case: str = "none"  # none|lower|upper

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
    max_lag_minutes: Optional[int] = None
    tolerance_pct: Optional[float] = None
    tolerance_abs: Optional[float] = None
    logic: Optional[Any] = None  # Python configs only

    # ordering
    order_by: Optional[List[str]] = None            # canonical column names (after alignment)
    order_by_source: Optional[List[str]] = None     # raw SQL expressions for source side
    order_by_target: Optional[List[str]] = None     # raw SQL expressions for target side


class TableCfg(BaseModel):
    """
    Per-table config with optional canonical column mapping.
    - dynamic_pattern=True enables wildcard-based expansion handled by the planner.
    - 'column_map' defines canonical columns available for alignment.
    - 'join_keys' must list aligned pairs: source[i] corresponds to target[i].
    """
    name: str
    dynamic_pattern: Optional[bool] = False
    source: QueryCfg
    target: QueryCfg
    join_keys: Dict[str, List[str]]  # {"source":[...], "target":[...]} same length
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


class ConfigModel(BaseModel):
    """
    Top-level config schema.
    """
    connections: ConnectionsCfg
    defaults: Optional[DefaultsCfg] = DefaultsCfg()
    tables: List[TableCfg]
    planning: Optional[PlanningCfg] = None
    alerts: Optional[AlertsCfg] = AlertsCfg()
