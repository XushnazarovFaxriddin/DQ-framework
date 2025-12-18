"""
Result dataclasses for checks and full run.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class CheckResult:
    table: str
    check_type: str
    status: str  # PASS | FAIL | SKIP | RECORDED
    details: Dict[str, Any] = field(default_factory=dict)
    severity: Optional[str] = None


@dataclass
class RunResult:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "PASS"  # PASS | FAIL | ERROR
    checks: List[CheckResult] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    overall_severity: str = "INFO"
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Legacy compatibility
    @property
    def overall_status(self) -> str:
        return self.status

    @overall_status.setter
    def overall_status(self, value: str) -> None:
        self.status = value

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def failed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    @property
    def skipped_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == "SKIP")

    @property
    def recorded_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == "RECORDED")

    def add_check(self, result: CheckResult) -> None:
        """Add a check result and update overall status."""
        self.checks.append(result)
        if result.status == "FAIL":
            self.status = "FAIL"
        if result.table not in self.tables:
            self.tables.append(result.table)

    def finalize(self) -> None:
        """Finalize the run result with timing and status."""
        if self.started_at and not self.completed_at:
            self.completed_at = datetime.utcnow()
        if self.started_at and self.completed_at:
            self.duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
