"""
Planner with threaded execution.

Responsibilities
----------------
1) Build an executable Plan from a validated ConfigModel:
   - Optional partition fan-out (rolling_days, rolling_hours, range)
   - Jinja2 templating support in QueryCfg fields:
       {{ env }}, {{ run_label }}, {{ partition_start_iso }}, {{ partition_end_iso }}
   - (Hook) Dynamic pattern expansion could be added here later

2) Execute the plan:
   - Table-level parallelism via ThreadPoolExecutor (concurrency_tables)
   - Optional per-table check-level parallelism (concurrency_checks)
   - Per-table and per-check timeouts (table_timeout_sec, check_timeout_sec)
   - Structured logging of lifecycle events and results

3) Pass hashing policy to checks:
   - Each check receives cfg.defaults.hashing

Inputs
------
- cfg: ConfigModel          (already validated by pydantic)
- vars_map: Dict[str, Any]  (from CLI --vars/--env/--run_label; may include concurrency/timeouts)

Outputs
-------
- Plan.run() -> Dict[str, Any] with:
    overall_status: "PASS"/"FAIL"
    stats: {pass, fail, skip}
    results: [CheckResult as dict, ...]

Notes
-----
- Alerts are dispatched at the end via alerts.dispatcher.dispatch_alerts
- For very large datasets, prefer using partitions + filters in queries to limit per-task workload
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, Future, TimeoutError

from jinja2 import Template

from src.runtime.context import build_run_context, RunContext
from src.runtime.results import CheckResult, RunResult
from src.runtime.registry import CHECKS
from src.runtime.results_persistence import persist_run_results
from src.utils.logger import log, ContextLogger
from src.utils.severity import highest_severity
from src.compiler.schema import ConfigModel, TableCfg, CheckCfg, QueryCfg, PlanningCfg


# ----------------------------
# Templating helpers (Jinja2)
# ----------------------------


def _render_text(text: Optional[str], ctx: Dict[str, Any]) -> Optional[str]:
    """Render a text with Jinja2 if it contains templates; return unchanged otherwise."""
    if text is None:
        return None
    s = text.strip()
    if not s:
        return s
    if "{{" in s and "}}" in s:
        return Template(s).render(**ctx)
    return s


def _render_query_cfg(q: QueryCfg, ctx: Dict[str, Any]) -> QueryCfg:
    """Render table/select/query strings of QueryCfg using templating context."""
    return QueryCfg(
        table=_render_text(q.table, ctx) if q.table else None,
        select=_render_text(q.select, ctx) if q.select else None,
        query=_render_text(q.query, ctx) if q.query else None,
        order_by=q.order_by,
        filters=_render_text(q.filters, ctx) if q.filters else None,
    )


# ----------------------------
# Partition windows
# ----------------------------


@dataclass(frozen=True)
class PartitionWindow:
    start: datetime
    end: datetime


def _default_single_window(now: datetime) -> List[PartitionWindow]:
    """Single non-partitioned window for simplicity (start at midnight UTC)."""
    return [
        PartitionWindow(
            start=now.replace(hour=0, minute=0, second=0, microsecond=0), end=now
        )
    ]


def _partition_windows(
    pcfg: Optional[PlanningCfg], now: datetime
) -> List[PartitionWindow]:
    """Compute list of partition windows based on planning config."""
    if not pcfg or not pcfg.partitions:
        return _default_single_window(now)

    p = pcfg.partitions
    mode = str(p.get("mode", "none") or "none").lower()
    window = int(p.get("window", 1) or 1)

    if mode == "rolling_days":
        end = now
        start = now - timedelta(days=window)
        return [PartitionWindow(start=start, end=end)]

    if mode == "rolling_hours":
        end = now
        start = now - timedelta(hours=window)
        return [PartitionWindow(start=start, end=end)]

    if mode == "range":
        st = datetime.fromisoformat(str(p["start"])).astimezone(timezone.utc)
        en = datetime.fromisoformat(str(p["end"])).astimezone(timezone.utc)
        return [PartitionWindow(start=st, end=en)]

    # Fallback: no partitions
    return _default_single_window(now)


# ----------------------------
# Execution units & Plan
# ----------------------------


@dataclass
class TableUnit:
    """
    A concrete execution unit for a single table + a specific partition window.
    QueryCfg fields are rendered (templated) for the given partition context.
    """

    table_cfg: TableCfg
    partition: Optional[PartitionWindow] = None


@dataclass
class Plan:
    """
    Threaded execution plan.
    """

    cfg: ConfigModel
    vars_map: Dict[str, Any]
    tables: List[TableUnit] = field(default_factory=list)
    context: Optional[RunContext] = None

    # ----------------------------
    # Public API
    # ----------------------------

    def run(self) -> RunResult:
        """
        Execute all TableUnits in parallel (configurable concurrency).
        - Submits each table_unit to the thread pool
        - Gathers results and computes overall status
        - Dispatches alerts at the end
        """
        self._ensure_context()
        run_start = datetime.now(timezone.utc)

        # Concurrency knobs
        concurrency_tables = int(self.vars_map.get("concurrency", 4))
        concurrency_checks = int(self.vars_map.get("concurrency_checks", 1))
        table_timeout_sec = _parse_optional_int(self.vars_map.get("table_timeout_sec"))
        check_timeout_sec = _parse_optional_int(self.vars_map.get("check_timeout_sec"))
        max_rows_preview = int(self.vars_map.get("max_rows_preview", 1000))

        log(
            "execution.start",
            table_units=len(self.tables),
            concurrency_tables=concurrency_tables,
            concurrency_checks=concurrency_checks,
            table_timeout_sec=table_timeout_sec,
            check_timeout_sec=check_timeout_sec,
            max_rows_preview=max_rows_preview,
        )

        all_results: List[CheckResult] = []

        # Submit table units to thread pool
        with ThreadPoolExecutor(max_workers=max(1, concurrency_tables)) as pool:
            fut_to_tu: Dict[Future, TableUnit] = {}
            for tu in self.tables:
                fut = pool.submit(
                    self._run_table_unit, tu, concurrency_checks, check_timeout_sec
                )
                fut_to_tu[fut] = tu
                log(
                    "table.submitted",
                    table=tu.table_cfg.name,
                    # partition=_part_dict(tu.partition),
                )

            for fut in as_completed(fut_to_tu):
                tu = fut_to_tu[fut]
                try:
                    # Optional per-table timeout
                    results: List[CheckResult] = (
                        fut.result(timeout=table_timeout_sec)
                        if table_timeout_sec
                        else fut.result()
                    )
                    all_results.extend(results)
                except TimeoutError:
                    # Mark the entire table unit as failed due to timeout
                    all_results.append(
                        CheckResult(
                            table=tu.table_cfg.name,
                            check_type="__table__",
                            status="FAIL",
                            details={
                                "error": "table_timeout",
                                "timeout_sec": table_timeout_sec,
                                # "partition": _part_dict(tu.partition),
                            },
                        )
                    )
                    log(
                        "table.timeout",
                        level="ERROR",
                        table=tu.table_cfg.name,
                        timeout_sec=table_timeout_sec,
                        # partition=_part_dict(tu.partition),
                    )
                except Exception as e:
                    # Mark as failed but let others continue
                    all_results.append(
                        CheckResult(
                            table=tu.table_cfg.name,
                            check_type="__table__",
                            status="FAIL",
                            details={
                                "error": str(e),
                                # "partition": _part_dict(tu.partition),
                            },
                        )
                    )
                    log(
                        "table.error",
                        level="ERROR",
                        table=tu.table_cfg.name,
                        error=str(e),
                        # partition=_part_dict(tu.partition),
                    )

        # Aggregate overall
        for result in all_results:
            if result.status == "FAIL" and not result.severity:
                result.severity = "WARNING"
        metadata: Dict[str, Any] = {
            "env": self.context.env,
            "run_label": self.context.run_label,
            "config_file": self.vars_map.get("config_file"),
        }
        run = RunResult(checks=all_results, metadata=metadata)
        if any(c.status == "FAIL" for c in all_results):
            run.overall_status = "FAIL"
        run.overall_severity = highest_severity(
            *(c.severity for c in all_results if c.status == "FAIL")
        )

        stats = {
            "pass": sum(c.status == "PASS" for c in all_results),
            "fail": sum(c.status == "FAIL" for c in all_results),
            "skip": sum(c.status == "SKIP" for c in all_results),
        }
        log("execution.finish", overall_status=run.overall_status, stats=stats)

        run_end = datetime.now(timezone.utc)
        run.metadata.update(
            {
                "run_start": run_start.isoformat(),
                "run_end": run_end.isoformat(),
            }
        )
        try:
            persist_run_results(
                self.cfg.results_storage,
                context=self.context,
                run=run,
                checks=all_results,
                run_start=run_start,
                run_end=run_end,
                stats=stats,
            )
        except Exception as exc:
            log("results.persistence.error", level="WARNING", error=str(exc))

        try:
            from src.alerts.dispatcher import dispatch_alerts

            dispatch_alerts(self.cfg, run)
        except Exception as e:
            log("alerts.dispatch.error", level="ERROR", error=str(e))

        return run

    # ----------------------------
    # Internals
    # ----------------------------

    def _ensure_context(self) -> None:
        """Build connection context lazily (URIs from env + connector pair)."""
        if self.context is None:
            self.context = build_run_context(self.cfg, self.vars_map)
            log(
                "context.ready",
                source_engine=self.context.engines[0],
                target_engine=self.context.engines[1],
            )

    def _run_table_unit(
        self, tu: TableUnit, concurrency_checks: int, check_timeout_sec: Optional[int]
    ) -> List[CheckResult]:
        """
        Run all checks for a given table unit.
        Optionally parallelize checks within the table using a per-table thread pool.
        """
        cl = ContextLogger(
            table=tu.table_cfg.name, 
            # partition=_part_dict(tu.partition)
        )
        cl.log("table.start")

        # Prepare runner partials for each check
        runners: List[Tuple[CheckCfg, Any]] = []
        for chk_cfg in tu.table_cfg.checks:
            runners.append((chk_cfg, self._make_check_runner(tu.table_cfg, chk_cfg)))

        # Execute checks (parallel or sequential)
        results: List[CheckResult] = []
        if concurrency_checks <= 1 or len(runners) <= 1:
            # Sequential
            for chk_cfg, runner in runners:
                results.append(
                    self._execute_check_runner(
                        tu.table_cfg, chk_cfg, runner, cl, check_timeout_sec
                    )
                )
        else:
            # Parallel within table
            with ThreadPoolExecutor(max_workers=max(1, concurrency_checks)) as pool:
                fut_to_chk: Dict[Future, Tuple[CheckCfg, Any]] = {}
                for chk_cfg, runner in runners:
                    fut = pool.submit(
                        self._execute_check_runner,
                        tu.table_cfg,
                        chk_cfg,
                        runner,
                        cl,
                        check_timeout_sec,
                    )
                    fut_to_chk[fut] = (chk_cfg, runner)
                    cl.log("check.submitted", check_type=chk_cfg.type)

                for fut in as_completed(fut_to_chk):
                    chk_cfg, _ = fut_to_chk[fut]
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        cl.log(
                            "check.pool.error",
                            level="ERROR",
                            check_type=chk_cfg.type,
                            error=str(e),
                        )
                        results.append(
                            CheckResult(
                                table=tu.table_cfg.name,
                                check_type=chk_cfg.type,
                                status="FAIL",
                                details={"error": str(e)},
                            )
                        )

        cl.log(
            "table.finish",
            summary={
                "pass": sum(r.status == "PASS" for r in results),
                "fail": sum(r.status == "FAIL" for r in results),
                "skip": sum(r.status == "SKIP" for r in results),
            },
        )
        return results

    def _make_check_runner(self, table: TableCfg, chk_cfg: CheckCfg):
        """
        Create a bound runner instance for a given check type.
        Unknown types are represented with a lambda producing SKIP.
        """
        runner_cls = CHECKS.get(chk_cfg.type)
        if runner_cls is None:

            def _skip_runner():
                return CheckResult(
                    table=table.name,
                    check_type=chk_cfg.type,
                    status="SKIP",
                    details={"reason": "unknown_check_type"},
                )

            return _skip_runner

        # Instantiate the runner with required dependencies
        runner = runner_cls(
            table_cfg=table,
            check_cfg=chk_cfg,
            source=self.context.source,
            target=self.context.target,
            vars_map=self.vars_map,
            hashing=self.cfg.defaults.hashing,
            results_storage=self.cfg.results_storage,
        )

        def _runner():
            return runner.run()

        return _runner

    def _execute_check_runner(
        self,
        table: TableCfg,
        chk_cfg: CheckCfg,
        runner_callable,
        cl: ContextLogger,
        timeout_sec: Optional[int],
    ) -> CheckResult:
        """
        Execute a single check runner with optional timeout.
        On failure/timeout, returns a FAIL CheckResult but does not raise.
        """
        # Fast path without extra thread for timeout
        if not timeout_sec or timeout_sec <= 0:
            try:
                cl2 = cl.bind(check_type=chk_cfg.type)
                cl2.log("check.start")
                res = runner_callable()
                cl2.log("check.finish", status=res.status, details=res.details)
                return res
            except Exception as e:
                cl.log(
                    "check.error", level="ERROR", check_type=chk_cfg.type, error=str(e)
                )
                return CheckResult(
                    table=table.name,
                    check_type=chk_cfg.type,
                    status="FAIL",
                    details={"error": str(e)},
                )

        # With timeout, run the runner in a mini thread pool
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _safe_run_callable,
                runner_callable,
                table.name,
                chk_cfg.type,
                cl,
            )
        try:
            return future.result(timeout=timeout_sec)
        except TimeoutError:
            cl.log(
                "check.timeout",
                level="ERROR",
                check_type=chk_cfg.type,
                timeout_sec=timeout_sec,
            )
            return CheckResult(
                table=table.name,
                check_type=chk_cfg.type,
                status="FAIL",
                details={"error": "check_timeout", "timeout_sec": timeout_sec},
            )


# ----------------------------
# Utilities
# ----------------------------


def _parse_optional_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _part_dict(pw: Optional[PartitionWindow]) -> Optional[Dict[str, str]]:
    if not pw:
        return None
    return {"start": pw.start.isoformat(), "end": pw.end.isoformat()}


def _safe_run_callable(
    fn, table_name: str, check_type: str, cl: ContextLogger
) -> CheckResult:
    """
    Execute a check runner callable, capturing exceptions into FAIL results.
    Used when a timeout is requested.
    """
    try:
        cl2 = cl.bind(check_type=check_type)
        cl2.log("check.start")
        res = fn()
        cl2.log("check.finish", status=res.status, details=res.details)
        return res
    except Exception as e:
        cl.log("check.error", level="ERROR", check_type=check_type, error=str(e))
        return CheckResult(
            table=table_name,
            check_type=check_type,
            status="FAIL",
            details={"error": str(e)},
        )


# ----------------------------
# Public builder
# ----------------------------


def build_plan(cfg: ConfigModel, vars_map: Dict[str, Any]) -> Plan:
    """
    Build a Plan with (optional) partition fan-out and templated queries.
    For each partition window, produce a TableUnit with QueryCfg rendered for that window.
    """
    now = datetime.now(timezone.utc)
    windows = _partition_windows(cfg.planning, now)

    log(
        "plan.build.start",
        windows=len(windows),
        planning_mode=(
            cfg.planning.partitions.get("mode")
            if cfg.planning and cfg.planning.partitions
            else "none"
        ),
    )

    units: List[TableUnit] = []
    for t in cfg.tables:
        for w in windows:
            ctx = {
                "env": vars_map.get("env"),
                "run_label": vars_map.get("run_label"),
                "partition_start_iso": w.start.isoformat(),
                "partition_end_iso": w.end.isoformat(),
                **vars_map,
            }
            # Render source/target
            ts = _render_query_cfg(t.source, ctx)
            tt = _render_query_cfg(t.target, ctx)

            t_copy = TableCfg(
                name=t.name,
                dynamic_pattern=t.dynamic_pattern,
                source=ts,
                target=tt,
                column_map=t.column_map,
                checks=t.checks,
            )
            units.append(TableUnit(table_cfg=t_copy, partition=w))

    log("plan.build.done", table_units=len(units))
    return Plan(cfg=cfg, vars_map=vars_map, tables=units)
