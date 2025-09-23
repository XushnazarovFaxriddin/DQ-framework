from abc import ABC, abstractmethod

from src.compiler.schema import TableCfg, CheckCfg, HashingCfg
from src.runtime.results import CheckResult


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
    ) -> None:
        self.table_cfg = table_cfg
        self.check_cfg = check_cfg
        self.source = source
        self.target = target
        self.vars_map = vars_map
        self.hashing = hashing or HashingCfg()

    @abstractmethod
    def run(self) -> CheckResult: ...
