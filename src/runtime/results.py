"""
Result dataclasses for checks and full run.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CheckResult:
    table: str
    check_type: str
    status: str               # PASS | FAIL | SKIP
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    overall_status: str = "PASS"
    checks: List[CheckResult] = field(default_factory=list)
