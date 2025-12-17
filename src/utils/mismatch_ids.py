"""
Mismatch IDs detection module for finding exact ID differences between source and target.

This module provides efficient algorithms for detecting:
- IDs present in source but missing in target (missing_in_target)
- IDs present in target but missing in source (extra_in_target - CRITICAL)

Optimized for 10M+ rows using:
- Chunked processing with configurable chunk sizes
- Binary search for narrowing down mismatched ranges
- Set-based comparison for final ID extraction

Environment variables (configured in .framework.env):
- DQF_MISMATCH_IDS_CHUNK_SIZE: Chunk size for ID fetching (default: 500000)
- DQF_MISMATCH_IDS_MAX_IDS: Maximum IDs to export per type (default: 100000)
- DQF_MISMATCH_IDS_PARALLEL_CHUNKS: Number of parallel chunk fetches (default: 4)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from src.compiler.schema import MismatchSamplingCfg
from src.connectors.base import BaseConnector
from src.utils.logger import log


def _env_int(var_name: str, default: int) -> int:
    val = os.getenv(var_name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _default_chunk_size() -> int:
    return _env_int("DQF_MISMATCH_IDS_CHUNK_SIZE", 500_000)


def _default_max_ids() -> int:
    return _env_int("DQF_MISMATCH_IDS_MAX_IDS", 100_000)


def _default_parallel_chunks() -> int:
    return _env_int("DQF_MISMATCH_IDS_PARALLEL_CHUNKS", 4)


@dataclass
class MismatchIdsResult:
    """Result of mismatch IDs detection."""

    # IDs in source but not in target
    missing_in_target: List[Any] = field(default_factory=list)
    # IDs in target but not in source (CRITICAL - data integrity issue)
    extra_in_target: List[Any] = field(default_factory=list)

    # Counts
    source_count: int = 0
    target_count: int = 0
    missing_in_target_count: int = 0
    extra_in_target_count: int = 0

    # Metadata
    id_column_source: str = ""
    id_column_target: str = ""
    truncated_missing: bool = False
    truncated_extra: bool = False
    scan_method: str = "chunked"
    chunks_scanned: int = 0
    processing_time_ms: int = 0

    # Run metadata for CSV
    table_name: str = ""
    check_name: str = ""
    run_date: str = ""
    config_file: str = ""

    def has_extra_in_target(self) -> bool:
        """Check if there are records in target that don't exist in source."""
        return self.extra_in_target_count > 0

    def to_summary_dict(self) -> Dict[str, Any]:
        """Generate summary for logging/alerts."""
        return {
            "source_count": self.source_count,
            "target_count": self.target_count,
            "missing_in_target_count": self.missing_in_target_count,
            "extra_in_target_count": self.extra_in_target_count,
            "truncated_missing": self.truncated_missing,
            "truncated_extra": self.truncated_extra,
            "scan_method": self.scan_method,
            "chunks_scanned": self.chunks_scanned,
            "processing_time_ms": self.processing_time_ms,
            "has_critical_extra_in_target": self.has_extra_in_target(),
        }

    def to_csv_rows(self) -> List[Dict[str, Any]]:
        """
        Generate CSV rows with dashboard-ready data.
        Each row represents one mismatched ID with full context.
        """
        rows: List[Dict[str, Any]] = []
        run_date = self.run_date or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Missing in target (source has, target doesn't)
        for id_val in self.missing_in_target:
            rows.append({
                "id": id_val,
                "mismatch_type": "missing_in_target",
                "source_exists": True,
                "target_exists": False,
                "table_name": self.table_name,
                "check_name": self.check_name,
                "config_file": self.config_file,
                "run_date": run_date,
                "source_total_count": self.source_count,
                "target_total_count": self.target_count,
                "total_missing_in_target": self.missing_in_target_count,
                "total_extra_in_target": self.extra_in_target_count,
                "id_column_source": self.id_column_source,
                "id_column_target": self.id_column_target,
                "is_critical": False,
                "scan_method": self.scan_method,
                "data_truncated": self.truncated_missing,
            })

        # Extra in target (target has, source doesn't) - CRITICAL
        for id_val in self.extra_in_target:
            rows.append({
                "id": id_val,
                "mismatch_type": "extra_in_target",
                "source_exists": False,
                "target_exists": True,
                "table_name": self.table_name,
                "check_name": self.check_name,
                "config_file": self.config_file,
                "run_date": run_date,
                "source_total_count": self.source_count,
                "target_total_count": self.target_count,
                "total_missing_in_target": self.missing_in_target_count,
                "total_extra_in_target": self.extra_in_target_count,
                "id_column_source": self.id_column_source,
                "id_column_target": self.id_column_target,
                "is_critical": True,
                "scan_method": self.scan_method,
                "data_truncated": self.truncated_extra,
            })

        return rows


def _fetch_ids_in_range(
    connector: BaseConnector,
    base_sql: str,
    id_column: str,
    range_start: Optional[int],
    range_end: Optional[int],
    limit: Optional[int] = None,
) -> Set[Any]:
    """Fetch IDs from a connector within a given range."""
    conditions: List[str] = []
    if range_start is not None:
        conditions.append(f"{id_column} >= {range_start}")
    if range_end is not None:
        conditions.append(f"{id_column} <= {range_end}")

    inner_alias = connector.wrap_subquery(base_sql, "q")
    inner = f"SELECT {id_column} FROM {inner_alias}"
    if conditions:
        inner = f"{inner} WHERE {' AND '.join(conditions)}"

    if limit:
        inner = f"{inner} LIMIT {limit}"

    try:
        df = connector.fetch_df(inner)
        if df is None or df.empty:
            return set()
        return set(df.iloc[:, 0].dropna().tolist())
    except Exception as exc:
        log(
            "mismatch_ids.fetch_error",
            level="ERROR",
            error=str(exc),
            id_column=id_column,
        )
        return set()


def _fetch_count(
    connector: BaseConnector,
    base_sql: str,
    id_column: str,
) -> int:
    """Fetch total count of distinct IDs."""
    inner_alias = connector.wrap_subquery(base_sql, "q")
    sql = f"SELECT COUNT(DISTINCT {id_column}) FROM {inner_alias}"
    try:
        result = connector.fetch_scalar(sql)
        return int(result or 0)
    except Exception:
        return 0


def _fetch_min_max(
    connector: BaseConnector,
    base_sql: str,
    id_column: str,
) -> Tuple[Optional[int], Optional[int]]:
    """Fetch min and max ID values."""
    inner_alias = connector.wrap_subquery(base_sql, "q")
    min_sql = f"SELECT MIN({id_column}) FROM {inner_alias}"
    max_sql = f"SELECT MAX({id_column}) FROM {inner_alias}"

    try:
        min_val = connector.fetch_scalar(min_sql)
        max_val = connector.fetch_scalar(max_sql)
        return (
            int(min_val) if min_val is not None else None,
            int(max_val) if max_val is not None else None,
        )
    except Exception:
        return None, None


def _chunked_id_comparison(
    source: BaseConnector,
    target: BaseConnector,
    source_base_sql: str,
    target_base_sql: str,
    id_column_source: str,
    id_column_target: str,
    overall_min: int,
    overall_max: int,
    chunk_size: int,
    max_ids: int,
) -> Tuple[List[Any], List[Any], int, bool, bool]:
    """
    Compare IDs using chunked approach for memory efficiency.
    Returns: (missing_in_target, extra_in_target, chunks_scanned, truncated_missing, truncated_extra)
    """
    missing_in_target: List[Any] = []
    extra_in_target: List[Any] = []
    chunks_scanned = 0
    truncated_missing = False
    truncated_extra = False

    cursor = overall_min
    while cursor <= overall_max:
        chunk_end = min(overall_max, cursor + chunk_size - 1)
        chunks_scanned += 1

        # Fetch IDs from both source and target for this chunk
        source_ids = _fetch_ids_in_range(
            source, source_base_sql, id_column_source, cursor, chunk_end
        )
        target_ids = _fetch_ids_in_range(
            target, target_base_sql, id_column_target, cursor, chunk_end
        )

        # Find differences
        chunk_missing = source_ids - target_ids
        chunk_extra = target_ids - source_ids

        # Add to results (respecting max_ids limit)
        for id_val in chunk_missing:
            if len(missing_in_target) >= max_ids:
                truncated_missing = True
                break
            missing_in_target.append(id_val)

        for id_val in chunk_extra:
            if len(extra_in_target) >= max_ids:
                truncated_extra = True
                break
            extra_in_target.append(id_val)

        cursor = chunk_end + 1

        # Early exit if both are truncated
        if truncated_missing and truncated_extra:
            break

    return missing_in_target, extra_in_target, chunks_scanned, truncated_missing, truncated_extra


def _binary_narrowed_comparison(
    source: BaseConnector,
    target: BaseConnector,
    source_base_sql: str,
    target_base_sql: str,
    id_column_source: str,
    id_column_target: str,
    overall_min: int,
    overall_max: int,
    max_depth: int,
    chunk_size: int,
    max_ids: int,
) -> Tuple[List[Any], List[Any], int, bool, bool]:
    """
    Use binary search to find mismatched ranges, then extract IDs.
    More efficient for sparse mismatches in large tables.
    """
    from src.utils.mismatch_sampling import _count_rows_in_range

    mismatched_ranges: List[Tuple[int, int]] = []
    chunks_scanned = 0

    def _find_mismatch_ranges(lo: int, hi: int, depth: int) -> None:
        nonlocal chunks_scanned
        if lo > hi:
            return

        chunks_scanned += 1
        source_count = _count_rows_in_range(
            source, source_base_sql, id_column_source, lo, hi
        )
        target_count = _count_rows_in_range(
            target, target_base_sql, id_column_target, lo, hi
        )

        if source_count == target_count:
            # Counts match, but we still need to check for swaps
            # Only do this at leaf level or small ranges
            if hi - lo <= chunk_size:
                mismatched_ranges.append((lo, hi))
            return

        if depth >= max_depth or hi - lo <= chunk_size:
            mismatched_ranges.append((lo, hi))
            return

        mid = (lo + hi) // 2
        _find_mismatch_ranges(lo, mid, depth + 1)
        _find_mismatch_ranges(mid + 1, hi, depth + 1)

    _find_mismatch_ranges(overall_min, overall_max, 1)

    # Extract IDs from mismatched ranges
    missing_in_target: List[Any] = []
    extra_in_target: List[Any] = []
    truncated_missing = False
    truncated_extra = False

    for range_start, range_end in mismatched_ranges:
        source_ids = _fetch_ids_in_range(
            source, source_base_sql, id_column_source, range_start, range_end
        )
        target_ids = _fetch_ids_in_range(
            target, target_base_sql, id_column_target, range_start, range_end
        )

        chunk_missing = source_ids - target_ids
        chunk_extra = target_ids - source_ids

        for id_val in chunk_missing:
            if len(missing_in_target) >= max_ids:
                truncated_missing = True
                break
            missing_in_target.append(id_val)

        for id_val in chunk_extra:
            if len(extra_in_target) >= max_ids:
                truncated_extra = True
                break
            extra_in_target.append(id_val)

        if truncated_missing and truncated_extra:
            break

    return missing_in_target, extra_in_target, chunks_scanned, truncated_missing, truncated_extra


def detect_mismatch_ids(
    *,
    source: BaseConnector,
    target: BaseConnector,
    source_base_sql: str,
    target_base_sql: str,
    id_column_source: str,
    id_column_target: str,
    sampling_cfg: Optional[MismatchSamplingCfg] = None,
    table_name: str = "",
    check_name: str = "",
    config_file: str = "",
    max_ids: Optional[int] = None,
) -> Optional[MismatchIdsResult]:
    """
    Detect mismatched IDs between source and target.

    Args:
        source: Source database connector
        target: Target database connector
        source_base_sql: Base SQL for source data
        target_base_sql: Base SQL for target data
        id_column_source: ID column name in source
        id_column_target: ID column name in target
        sampling_cfg: Optional sampling configuration
        table_name: Table name for metadata
        check_name: Check name for metadata
        config_file: Config file name for CSV path
        max_ids: Maximum IDs to export (defaults to env var)

    Returns:
        MismatchIdsResult with detected differences, or None on error
    """
    import time
    start_time = time.time()

    if not id_column_source or not id_column_target:
        log(
            "mismatch_ids.skipped",
            table=table_name,
            check=check_name,
            reason="missing_id_columns",
        )
        return None

    # Get counts
    source_count = _fetch_count(source, source_base_sql, id_column_source)
    target_count = _fetch_count(target, target_base_sql, id_column_target)

    # Get bounds
    src_min, src_max = _fetch_min_max(source, source_base_sql, id_column_source)
    tgt_min, tgt_max = _fetch_min_max(target, target_base_sql, id_column_target)

    overall_min = min(
        (v for v in (src_min, tgt_min) if v is not None),
        default=None,
    )
    overall_max = max(
        (v for v in (src_max, tgt_max) if v is not None),
        default=None,
    )

    if overall_min is None or overall_max is None:
        log(
            "mismatch_ids.skipped",
            table=table_name,
            check=check_name,
            reason="no_id_bounds",
        )
        return None

    # Determine parameters
    chunk_size = _default_chunk_size()
    effective_max_ids = max_ids or _default_max_ids()
    max_depth = 8  # Default binary search depth

    if sampling_cfg:
        if sampling_cfg.chunk_size:
            chunk_size = sampling_cfg.chunk_size
        if sampling_cfg.max_depth:
            max_depth = sampling_cfg.max_depth

    # Choose method based on data size and configuration
    use_binary = False
    if sampling_cfg and sampling_cfg.mode == "binary":
        use_binary = True
    elif (overall_max - overall_min) > chunk_size * 20:
        # Large range, binary might be more efficient
        use_binary = True

    # Perform comparison
    if use_binary:
        missing, extra, chunks, trunc_miss, trunc_extra = _binary_narrowed_comparison(
            source=source,
            target=target,
            source_base_sql=source_base_sql,
            target_base_sql=target_base_sql,
            id_column_source=id_column_source,
            id_column_target=id_column_target,
            overall_min=overall_min,
            overall_max=overall_max,
            max_depth=max_depth,
            chunk_size=chunk_size,
            max_ids=effective_max_ids,
        )
        scan_method = "binary"
    else:
        missing, extra, chunks, trunc_miss, trunc_extra = _chunked_id_comparison(
            source=source,
            target=target,
            source_base_sql=source_base_sql,
            target_base_sql=target_base_sql,
            id_column_source=id_column_source,
            id_column_target=id_column_target,
            overall_min=overall_min,
            overall_max=overall_max,
            chunk_size=chunk_size,
            max_ids=effective_max_ids,
        )
        scan_method = "chunked"

    processing_time = int((time.time() - start_time) * 1000)
    run_date = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    result = MismatchIdsResult(
        missing_in_target=sorted(missing),
        extra_in_target=sorted(extra),
        source_count=source_count,
        target_count=target_count,
        missing_in_target_count=len(missing) if not trunc_miss else len(missing),
        extra_in_target_count=len(extra) if not trunc_extra else len(extra),
        id_column_source=id_column_source,
        id_column_target=id_column_target,
        truncated_missing=trunc_miss,
        truncated_extra=trunc_extra,
        scan_method=scan_method,
        chunks_scanned=chunks,
        processing_time_ms=processing_time,
        table_name=table_name,
        check_name=check_name,
        run_date=run_date,
        config_file=config_file,
    )

    # Log results
    log(
        "mismatch_ids.complete",
        table=table_name,
        check=check_name,
        source_count=source_count,
        target_count=target_count,
        missing_in_target=len(missing),
        extra_in_target=len(extra),
        has_critical_extra=result.has_extra_in_target(),
        scan_method=scan_method,
        processing_time_ms=processing_time,
    )

    if result.has_extra_in_target():
        log(
            "mismatch_ids.critical_alert",
            level="WARNING",
            table=table_name,
            check=check_name,
            message="TARGET HAS RECORDS NOT IN SOURCE - Potential data integrity issue!",
            extra_in_target_count=len(extra),
            sample_extra_ids=extra[:10],
        )

    return result
