"""Row count parity check with mismatch IDs detection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.checks.base import BaseCheck
from src.compiler.schema import CheckCfg, ColumnMapEntry, MismatchSamplingCfg
from src.runtime.registry import register_check
from src.runtime.results import CheckResult
from src.utils.io import attach_csv_uri
from src.utils.logger import log
from src.utils.mismatch_ids import detect_mismatch_ids, MismatchIdsResult
from src.utils.mismatch_sampling import MismatchSamplingResult, sample_mismatch_ranges
from src.utils.sql import wrap_order_by


def _map_order_by(
    columns: Optional[List[str]],
    column_map: Optional[dict[str, ColumnMapEntry]],
    *,
    side: str,
) -> Optional[List[str]]:
    if not columns:
        return None
    if not column_map:
        return columns
    mapped: List[str] = []
    for canonical in columns:
        entry = column_map.get(canonical)
        if entry is None:
            mapped.append(canonical)
            continue
        mapped.append(entry.source if side == "source" else entry.target)
    return mapped


@register_check("row_count")
class RowCountCheck(BaseCheck):
    def run(self) -> CheckResult:
        source_base_sql = self.source.render_select_sql(self.table_cfg.source)
        target_base_sql = self.target.render_select_sql(self.table_cfg.target)

        order_by_source = self.check_cfg.order_by_source or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="source"
        )
        order_by_target = self.check_cfg.order_by_target or _map_order_by(
            self.check_cfg.order_by, self.table_cfg.column_map, side="target"
        )

        s_sql = wrap_order_by(source_base_sql, order_by_source)
        t_sql = wrap_order_by(target_base_sql, order_by_target)

        s_count = int(self.source.fetch_scalar(self.source.render_count_sql(s_sql)))
        t_count = int(self.target.fetch_scalar(self.target.render_count_sql(t_sql)))

        sampling_cfg = self.check_cfg.mismatch_sampling
        status = "PASS" if s_count == t_count else "FAIL"
        details = {"source_count": s_count, "target_count": t_count}

        id_source, id_target = _resolve_id_columns(self.check_cfg)
        config_summary = _build_config_summary(
            cfg=self.check_cfg,
            sampling_cfg=sampling_cfg,
            id_source=id_source,
            id_target=id_target,
        )
        if config_summary:
            details["config_summary"] = config_summary

        mismatch_result: Optional[MismatchSamplingResult] = None
        mismatch_ids_result: Optional[MismatchIdsResult] = None
        sampling_cfg = self.check_cfg.mismatch_sampling

        if status == "FAIL" and sampling_cfg:
            # Traditional range-based mismatch sampling
            mismatch_result = _maybe_sample_ranges(
                self,
                source_base_sql,
                target_base_sql,
            )
            if mismatch_result:
                details["mismatch_ranges"] = mismatch_result.summary(sampling_cfg.max_ranges)
                self.record_mismatch_sampling(
                    f"{self.table_cfg.name}.row_count", mismatch_result
                )
                if uri := self.persist_mismatch_csv(
                    f"{self.table_cfg.name}.row_count",
                    mismatch_result,
                ):
                    attach_csv_uri(details, uri)

            # Detect and export actual mismatch IDs
            mismatch_ids_result = _maybe_detect_mismatch_ids(
                self,
                source_base_sql,
                target_base_sql,
            )
            if mismatch_ids_result:
                # Get config file name from vars_map
                config_file = self.vars_map.get("config_file", "")
                self.persist_mismatch_ids(mismatch_ids_result, details, config_file)

        return CheckResult(
            table=self.table_cfg.name,
            check_type="row_count",
            status=status,
            details=details,
        )


def _maybe_sample_ranges(
    check: RowCountCheck,
    source_base_sql: str,
    target_base_sql: str,
) -> Optional[MismatchSamplingResult]:
    sampling_cfg = check.check_cfg.mismatch_sampling
    if not sampling_cfg:
        return None

    source_id, target_id = _resolve_id_columns(check.check_cfg)
    if not source_id or not target_id:
        log(
            "mismatch_sampling.skipped",
            table=check.table_cfg.name,
            check="row_count",
            reason="missing_id_column",
        )
        return None

    try:
        return sample_mismatch_ranges(
            source=check.source,
            target=check.target,
            source_base_sql=source_base_sql,
            target_base_sql=target_base_sql,
            id_column_source=source_id,
            id_column_target=target_id,
            sampling_cfg=sampling_cfg,
        )
    except Exception as exc:
        log(
            "mismatch_sampling.error",
            level="ERROR",
            table=check.table_cfg.name,
            check="row_count",
            error=str(exc),
        )
        return None


def _resolve_id_columns(cfg: CheckCfg) -> Tuple[Optional[str], Optional[str]]:
    default = cfg.id_column
    return (
        cfg.id_column_source or default,
        cfg.id_column_target or default,
    )


def _build_config_summary(
    *,
    cfg: CheckCfg,
    sampling_cfg: Optional[MismatchSamplingCfg],
    id_source: Optional[str],
    id_target: Optional[str],
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    if cfg.on:
        summary["on"] = cfg.on
    if cfg.tolerance_pct is not None:
        summary["tolerance_pct"] = cfg.tolerance_pct
    if cfg.tolerance_abs is not None:
        summary["tolerance_abs"] = cfg.tolerance_abs
    if id_source and id_target:
        if id_source == id_target:
            summary["id"] = id_source
        else:
            summary["src_id"] = id_source
            summary["tgt_id"] = id_target
    elif id_source or id_target:
        summary["id"] = id_source or id_target
    elif cfg.id_column:
        summary["id"] = cfg.id_column
    if sampling_cfg:
        summary["sample_mode"] = sampling_cfg.mode
        if sampling_cfg.mode == "chunk" and sampling_cfg.chunk_size:
            summary["chunk_size"] = sampling_cfg.chunk_size
    return summary


def _maybe_detect_mismatch_ids(
    check: RowCountCheck,
    source_base_sql: str,
    target_base_sql: str,
) -> Optional[MismatchIdsResult]:
    """
    Detect actual mismatch IDs between source and target.

    This identifies:
    - IDs in source but missing in target (missing_in_target)
    - IDs in target but missing in source (extra_in_target) - CRITICAL
    """
    sampling_cfg = check.check_cfg.mismatch_sampling
    if not sampling_cfg:
        return None

    source_id, target_id = _resolve_id_columns(check.check_cfg)
    if not source_id or not target_id:
        log(
            "mismatch_ids.skipped",
            table=check.table_cfg.name,
            check="row_count",
            reason="missing_id_column",
        )
        return None

    # Check if mismatch_ids export is enabled
    mismatch_ids_cfg = (
        check.results_storage_cfg.mismatch_ids
        if check.results_storage_cfg
        else None
    )
    if not mismatch_ids_cfg or not mismatch_ids_cfg.enabled:
        return None

    try:
        config_file = check.vars_map.get("config_file", "")
        return detect_mismatch_ids(
            source=check.source,
            target=check.target,
            source_base_sql=source_base_sql,
            target_base_sql=target_base_sql,
            id_column_source=source_id,
            id_column_target=target_id,
            sampling_cfg=sampling_cfg,
            table_name=check.table_cfg.name,
            check_name="row_count",
            config_file=config_file,
            max_ids=mismatch_ids_cfg.max_ids,
        )
    except Exception as exc:
        log(
            "mismatch_ids.error",
            level="ERROR",
            table=check.table_cfg.name,
            check="row_count",
            error=str(exc),
        )
        return None
