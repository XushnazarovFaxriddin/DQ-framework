"""Helpers to sample ID ranges after count mismatches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.compiler.schema import MismatchSamplingCfg
from src.connectors.base import BaseConnector


@dataclass
class RangeMismatch:
    range_start: int
    range_end: int
    source_count: int
    target_count: int

    @property
    def diff(self) -> int:
        return self.source_count - self.target_count

    def to_dict(self) -> Dict[str, int]:
        return {
            "range_start": self.range_start,
            "range_end": self.range_end,
            "source_count": self.source_count,
            "target_count": self.target_count,
            "diff": self.diff,
        }


@dataclass
class MismatchSamplingResult:
    mode: str
    ranges: List[RangeMismatch]
    scanned_segments: int
    max_scan_segments: int
    truncated: bool
    range_start: Optional[int]
    range_end: Optional[int]

    def summary(self, limit: int) -> List[Dict[str, int]]:
        limit = max(0, limit)
        sorted_ranges = sorted(self.ranges, key=lambda rng: abs(rng.diff), reverse=True)
        return [rng.to_dict() for rng in sorted_ranges[:limit]]

    def rows(self) -> List[Dict[str, int]]:
        return [rng.to_dict() for rng in self.ranges]


def sample_mismatch_ranges(
    *,
    source: BaseConnector,
    target: BaseConnector,
    source_base_sql: str,
    target_base_sql: str,
    id_column_source: str,
    id_column_target: str,
    sampling_cfg: MismatchSamplingCfg,
) -> Optional[MismatchSamplingResult]:
    if not id_column_source or not id_column_target or not sampling_cfg:
        return None

    bounds = _resolve_bounds(
        source=source,
        target=target,
        source_base_sql=source_base_sql,
        target_base_sql=target_base_sql,
        id_column_source=id_column_source,
        id_column_target=id_column_target,
        sampling_cfg=sampling_cfg,
    )
    if bounds is None:
        return None

    start, end = bounds
    if start > end:
        return None

    if sampling_cfg.mode == "chunk":
        return _chunk_scan(
            source=source,
            target=target,
            source_base_sql=source_base_sql,
            target_base_sql=target_base_sql,
            id_column_source=id_column_source,
            id_column_target=id_column_target,
            start=start,
            end=end,
            sampling_cfg=sampling_cfg,
        )
    return _binary_scan(
        source=source,
        target=target,
        source_base_sql=source_base_sql,
        target_base_sql=target_base_sql,
        id_column_source=id_column_source,
        id_column_target=id_column_target,
        start=start,
        end=end,
        sampling_cfg=sampling_cfg,
    )


def _resolve_bounds(
    *,
    source: BaseConnector,
    target: BaseConnector,
    source_base_sql: str,
    target_base_sql: str,
    id_column_source: str,
    id_column_target: str,
    sampling_cfg: MismatchSamplingCfg,
) -> Optional[Tuple[int, int]]:
    src_min, src_max = _query_min_max(
        connector=source, base_sql=source_base_sql, id_column=id_column_source
    )
    tgt_min, tgt_max = _query_min_max(
        connector=target, base_sql=target_base_sql, id_column=id_column_target
    )

    overall_min = min(
        (value for value in (src_min, tgt_min) if value is not None),
        default=None,
    )
    overall_max = max(
        (value for value in (src_max, tgt_max) if value is not None),
        default=None,
    )

    start = sampling_cfg.range_start if sampling_cfg.range_start is not None else overall_min
    end = sampling_cfg.range_end if sampling_cfg.range_end is not None else overall_max

    if start is None or end is None:
        return None

    return int(start), int(end)


def _query_min_max(
    *,
    connector: BaseConnector,
    base_sql: str,
    id_column: str,
) -> Tuple[Optional[int], Optional[int]]:
    alias = connector.wrap_subquery(base_sql, "q")
    min_sql = f"SELECT MIN({id_column}) FROM {alias}"
    max_sql = f"SELECT MAX({id_column}) FROM {alias}"
    min_val = connector.fetch_scalar(min_sql)
    max_val = connector.fetch_scalar(max_sql)
    return _coerce_int(min_val), _coerce_int(max_val)


def _coerce_int(value: Optional[object]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _count_rows_in_range(
    connector: BaseConnector,
    base_sql: str,
    id_column: str,
    start: Optional[int],
    end: Optional[int],
) -> int:
    conditions: List[str] = []
    if start is not None:
        conditions.append(f"{id_column} >= {start}")
    if end is not None:
        conditions.append(f"{id_column} <= {end}")

    inner_alias = connector.wrap_subquery(base_sql, "q")
    inner = f"SELECT * FROM {inner_alias}"
    if conditions:
        inner = f"{inner} WHERE {' AND '.join(conditions)}"

    sql = connector.render_count_sql(inner)
    return int(connector.fetch_scalar(sql) or 0)


def _chunk_scan(
    *,
    source: BaseConnector,
    target: BaseConnector,
    source_base_sql: str,
    target_base_sql: str,
    id_column_source: str,
    id_column_target: str,
    start: int,
    end: int,
    sampling_cfg: MismatchSamplingCfg,
) -> MismatchSamplingResult:
    chunk_size = sampling_cfg.chunk_size
    if chunk_size is None or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")

    max_chunks = max(1, sampling_cfg.max_scan_chunks)
    cursor = start
    ranges: List[RangeMismatch] = []
    scanned = 0
    truncated = False

    while cursor <= end:
        if scanned >= max_chunks:
            truncated = True
            break
        chunk_end = min(end, cursor + chunk_size - 1)
        source_count = _count_rows_in_range(
            source, source_base_sql, id_column_source, cursor, chunk_end
        )
        target_count = _count_rows_in_range(
            target, target_base_sql, id_column_target, cursor, chunk_end
        )
        scanned += 1
        if source_count != target_count:
            ranges.append(RangeMismatch(cursor, chunk_end, source_count, target_count))
        cursor = chunk_end + 1

    if cursor <= end:
        truncated = True

    return MismatchSamplingResult(
        mode="chunk",
        ranges=ranges,
        scanned_segments=scanned,
        max_scan_segments=max_chunks,
        truncated=truncated,
        range_start=start,
        range_end=end,
    )


def _binary_scan(
    *,
    source: BaseConnector,
    target: BaseConnector,
    source_base_sql: str,
    target_base_sql: str,
    id_column_source: str,
    id_column_target: str,
    start: int,
    end: int,
    sampling_cfg: MismatchSamplingCfg,
) -> MismatchSamplingResult:
    max_chunks = max(1, sampling_cfg.max_scan_chunks)
    max_depth = max(1, sampling_cfg.max_depth)
    ranges: List[RangeMismatch] = []
    scanned = 0
    truncated = False

    def _visit(lo: int, hi: int, depth: int) -> None:
        nonlocal scanned, truncated
        if lo > hi or scanned >= max_chunks:
            if scanned >= max_chunks:
                truncated = True
            return
        source_count = _count_rows_in_range(
            source, source_base_sql, id_column_source, lo, hi
        )
        target_count = _count_rows_in_range(
            target, target_base_sql, id_column_target, lo, hi
        )
        scanned += 1
        if source_count == target_count:
            return
        if depth >= max_depth or lo == hi:
            ranges.append(RangeMismatch(lo, hi, source_count, target_count))
            return
        mid = (lo + hi) // 2
        _visit(lo, mid, depth + 1)
        _visit(mid + 1, hi, depth + 1)

    _visit(start, end, depth=1)

    return MismatchSamplingResult(
        mode="binary",
        ranges=ranges,
        scanned_segments=scanned,
        max_scan_segments=max_chunks,
        truncated=truncated,
        range_start=start,
        range_end=end,
    )
