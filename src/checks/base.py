from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

from src.compiler.schema import (
    CheckCfg,
    HashingCfg,
    ResultsStorageCfg,
    TableCfg,
)
from src.runtime.results import CheckResult
from src.utils.io import persist_rows_csv, persist_mismatch_ids_csv, attach_mismatch_ids_uris
from src.utils.logger import log
from src.utils.mismatch_sampling import MismatchSamplingResult

if TYPE_CHECKING:
    from src.utils.mismatch_ids import MismatchIdsResult


@dataclass
class MismatchSamplingRecord:
    label: str
    result: MismatchSamplingResult


class BaseCheck(ABC):
    def __init__(
        self,
        *,
        table_cfg: TableCfg,
        check_cfg: CheckCfg,
        source,
        target,
        vars_map: dict,
        hashing: HashingCfg | None = None,
        results_storage: ResultsStorageCfg | None = None,
    ) -> None:
        self.table_cfg = table_cfg
        self.check_cfg = check_cfg
        self.source = source
        self.target = target
        self.vars_map = vars_map
        self.hashing = hashing or HashingCfg()
        self.results_storage_cfg = results_storage
        self._mismatch_sampling_records: List[MismatchSamplingRecord] = []

    @abstractmethod
    def run(self) -> CheckResult: ...

    def record_mismatch_sampling(self, label: str, result: MismatchSamplingResult) -> None:
        self._mismatch_sampling_records.append(MismatchSamplingRecord(label=label, result=result))

    def get_mismatch_sampling_records(self) -> Sequence[MismatchSamplingRecord]:
        return tuple(self._mismatch_sampling_records)

    def persist_mismatch_csv(
        self,
        label: str,
        sampling_result: Optional[MismatchSamplingResult],
    ) -> Optional[str]:
        if not sampling_result:
            return None
        cfg = (
            self.results_storage_cfg.mismatch_csv
            if self.results_storage_cfg
            else None
        )
        if not cfg or not cfg.enabled:
            return None
        rows = sampling_result.rows()
        if not rows:
            return None
        try:
            uri = persist_rows_csv(
                rows=rows,
                label=label,
                vars_map=self.vars_map,
                cfg=cfg,
            )
        except Exception as exc:
            log(
                "mismatch_csv.error",
                level="WARNING",
                table=self.table_cfg.name,
                check=self.check_cfg.type,
                label=label,
                error=str(exc),
            )
            return None
        if uri:
            log(
                "mismatch_csv.persist.ok",
                table=self.table_cfg.name,
                check=self.check_cfg.type,
                label=label,
                uri=uri,
            )
        return uri

    def persist_mismatch_ids(
        self,
        mismatch_ids_result: Optional["MismatchIdsResult"],
        details: Dict[str, Any],
        config_file: str = "",
    ) -> Optional[Dict[str, str]]:
        """
        Persist mismatch IDs to CSV and attach URIs to check details.

        Args:
            mismatch_ids_result: Result from detect_mismatch_ids()
            details: Check result details dict to attach URIs to
            config_file: Name of the config file for path template

        Returns:
            Dict of URIs if successful, None otherwise
        """
        if not mismatch_ids_result:
            return None

        cfg = (
            self.results_storage_cfg.mismatch_ids
            if self.results_storage_cfg
            else None
        )
        if not cfg or not cfg.enabled:
            return None

        try:
            uris = persist_mismatch_ids_csv(
                mismatch_result=mismatch_ids_result,
                cfg=cfg,
                config_file=config_file,
                check_name=self.check_cfg.type,
                table_name=self.table_cfg.name,
            )
            if uris:
                attach_mismatch_ids_uris(details, uris)

                # Add summary to details
                details["mismatch_ids_summary"] = mismatch_ids_result.to_summary_dict()

                # Mark if there are critical extra records in target
                if mismatch_ids_result.has_extra_in_target():
                    details["has_extra_in_target"] = True
                    details["extra_in_target_count"] = mismatch_ids_result.extra_in_target_count
                    log(
                        "mismatch_ids.critical_detected",
                        level="WARNING",
                        table=self.table_cfg.name,
                        check=self.check_cfg.type,
                        extra_in_target_count=mismatch_ids_result.extra_in_target_count,
                        message="CRITICAL: Target has records not present in source!",
                    )

            return uris
        except Exception as exc:
            log(
                "mismatch_ids.persist.error",
                level="WARNING",
                table=self.table_cfg.name,
                check=self.check_cfg.type,
                error=str(exc),
            )
            return None
