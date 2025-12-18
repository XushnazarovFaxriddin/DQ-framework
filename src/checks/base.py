from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

from src.compiler.schema import (
    CheckCfg,
    HashingCfg,
    ResultsStorageCfg,
    TableCfg,
)
from src.runtime.results import CheckResult
from src.utils.io import persist_mismatch_ids_csv, attach_mismatch_ids_uris
from src.utils.logger import log

if TYPE_CHECKING:
    from src.utils.mismatch_ids import MismatchIdsResult


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

    @abstractmethod
    def run(self) -> CheckResult: ...

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
