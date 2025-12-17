from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence

from src.compiler.schema import (
    CheckCfg,
    HashingCfg,
    ResultsStorageCfg,
    TableCfg,
)
from src.runtime.results import CheckResult
from src.utils.io import persist_rows_csv
from src.utils.logger import log
from src.utils.mismatch_sampling import MismatchSamplingResult


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
