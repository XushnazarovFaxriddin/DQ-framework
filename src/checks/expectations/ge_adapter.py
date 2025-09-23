"""
Great Expectations (GE) adapter for DQF.

Supported modes
---------------
1) Inline expectations (rules.expectations) on a Pandas dataset
   - We fetch a DataFrame via connector.fetch_df(sql) and execute expectations
   - Expectation spec format:
        rules:
          - expectations:
              - expectation_type: expect_column_values_to_not_be_null
                kwargs: { column: "id" }
              - expectation_type: expect_table_row_count_to_be_between
                kwargs: { min_value: 1 }
   - Optional: suite_file (YAML/JSON) containing {"expectations":[...]}

2) (Optional) GE Checkpoint (advanced)
   - checkpoint_file: Path to GE checkpoint YAML (relative to GE context dir or absolute)
   - gx_context_dir: Path to great_expectations/ (if not default)
   - variables: key/value map for template substitution in checkpoint (optional)
   - NOTE: This requires an existing GE context on disk and the checkpoint to reference a
           datasource/connector configured there.

Config fields (in CheckCfg.rules[0], unified for simplicity)
------------------------------------------------------------
- on: "source"|"target"                       # default: "source"
- query: "<SQL>"                              # optional, otherwise render from table_cfg
- limit: 5000                                 # optional limit for pandas-mode
- suite_file: "path/to/suite.yaml|json"       # optional for pandas-mode
- expectations: [ {expectation_type, kwargs}, ... ]  # optional inline
- checkpoint_file: "path/to/checkpoint.yml"   # optional (exclusive mode)
- gx_context_dir: "path/to/great_expectations" # optional (checkpoint mode)
- variables: { var1: value, ... }             # optional

Outcome
-------
- PASS if all expectations succeed (or checkpoint has no failures)
- FAIL otherwise, with details: failures, stats
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.utils.logger import log
from src.runtime.registry import register_check


def _load_suite_file(path: str) -> Dict[str, Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        import yaml  # type: ignore

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    elif ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        raise ValueError("suite_file must be .yaml/.yml or .json")
    if not isinstance(data, dict):
        raise ValueError("suite_file content must be a mapping")
    return data


def _collect_expectations_from_rules(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge `suite_file` (if present) + inline `expectations` into a single suite dict.
    """
    suite: Dict[str, Any] = {"expectations": []}
    if not rules:
        return suite

    cfg = rules[0] or {}
    # suite_file
    suite_file = cfg.get("suite_file")
    if suite_file:
        loaded = _load_suite_file(suite_file)
        exps = loaded.get("expectations") or []
        if not isinstance(exps, list):
            raise ValueError("suite_file: 'expectations' must be a list")
        suite["expectations"].extend(exps)

    # inline expectations
    inline = cfg.get("expectations") or []
    if inline:
        if not isinstance(inline, list):
            raise ValueError("'expectations' must be a list")
        suite["expectations"].extend(inline)

    return suite


def _pandas_expectations_runner(
    df, expectations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Execute expectations on a Pandas dataset using either:
      - great_expectations.dataset.PandasDataset (legacy)
      - or ge.from_pandas(..) if available
    Returns a summary dict with pass/fail counts and failed items.
    """
    # Try modern API first
    try:
        import great_expectations as ge  # type: ignore
    except Exception:
        raise ImportError("great_expectations is not installed")

    ds = None
    # Prefer ge.dataset.PandasDataset if available (stable 'expect_*' API)
    try:
        from great_expectations.dataset import PandasDataset  # type: ignore

        ds = PandasDataset(df)
    except Exception:
        # Fallback to ge.from_pandas (GX)
        try:
            ds = ge.from_pandas(df)  # type: ignore
        except Exception as e:
            raise RuntimeError(f"Failed to create GE dataset/validator: {e}")

    failures: List[Dict[str, Any]] = []
    total = 0
    passed = 0

    for item in expectations:
        et = item.get("expectation_type")
        kwargs = item.get("kwargs", {}) or {}
        if not et:
            raise ValueError("Each expectation must have 'expectation_type'")
        total += 1
        # Invoke method dynamically: expect_* on ds
        fn = getattr(ds, et, None)
        if fn is None:
            # Many APIs expose expectations via 'expect_*' even in GX
            # If not found, try ds["expectation_type"] attr approach (rare)
            raise ValueError(f"Unknown expectation method: {et}")

        res = fn(**kwargs)  # returns GE result-like object or dict
        success = False
        details = {}
        try:
            if isinstance(res, dict) and "success" in res:
                success = bool(res.get("success"))
                details = {k: v for k, v in res.items() if k != "success"}
            else:
                # Some wrappers return ValidationResult objects
                success = bool(getattr(res, "success", False))
                details = {"result": getattr(res, "result", None)}
        except Exception:
            # Defensive parsing
            success = False
            details = {"raw": str(res)}

        if success:
            passed += 1
        else:
            failures.append({"expectation": et, "kwargs": kwargs, "details": details})

    return {
        "total": total,
        "passed": passed,
        "failed": len(failures),
        "failures": failures[:50],
    }


def _run_checkpoint(
    checkpoint_file: str,
    gx_context_dir: Optional[str],
    variables: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Run a GE checkpoint from a YAML file using DataContext.
    Returns a summary dict.
    """
    try:
        # GE v0.x DataContext
        from great_expectations.data_context import DataContext  # type: ignore
    except Exception as e:
        raise ImportError("great_expectations DataContext is not available") from e

    # Build context (explicit dir if provided)
    context = (
        DataContext(context_root_dir=gx_context_dir)
        if gx_context_dir
        else DataContext()
    )

    # Load checkpoint YAML and register/update
    import yaml  # type: ignore

    with open(checkpoint_file, "r", encoding="utf-8") as f:
        cp_yaml = yaml.safe_load(f)

    # Name required for add_or_update_checkpoint
    cp_name = (
        cp_yaml.get("name") or os.path.splitext(os.path.basename(checkpoint_file))[0]
    )
    cp_yaml["name"] = cp_name

    # Merge runtime variables if given (for template substitution)
    if variables:
        # GE does Jinja templating on YAML before materialization; provide at runtime if supported
        cp_yaml.setdefault("template_variables", {}).update(variables)

    # Register/update and run
    context.add_or_update_checkpoint(**cp_yaml)  # type: ignore
    result = context.run_checkpoint(checkpoint_name=cp_name)  # type: ignore

    # Parse checkpoint result
    has_failures = False
    failed_expectations: List[Dict[str, Any]] = []

    try:
        has_failures = bool(result["success"] is False)
        # Collect failed validations
        for vr in result.get("run_results", {}).values():
            v = vr.get("validation_result", {})
            if not v:
                continue
            for r in v.get("results", []):
                if not r.get("success", True):
                    failed_expectations.append(
                        {
                            "expectation_type": r.get("expectation_config", {}).get(
                                "expectation_type"
                            ),
                            "kwargs": r.get("expectation_config", {}).get("kwargs"),
                            "result": r.get("result"),
                        }
                    )
    except Exception:
        # Conservative
        has_failures = True

    return {
        "failed": len(failed_expectations),
        "failures": failed_expectations[:50],
        "success": not has_failures,
    }


register_check("ge_expectations")


class GECheckAdapter(BaseCheck):
    """
    Great Expectations adapter.
    """

    def run(self) -> CheckResult:
        # Extract one unified rule block (first rules item)
        rule = (self.check_cfg.rules or [{}])[0]
        side = str(rule.get("on", "source")).lower()
        limit = int(rule.get("limit", self.vars_map.get("max_rows_preview", 1000)))

        # Checkpoint mode?
        checkpoint_file = rule.get("checkpoint_file")
        if checkpoint_file:
            gx_dir = rule.get("gx_context_dir")
            variables = rule.get("variables")
            try:
                summary = _run_checkpoint(checkpoint_file, gx_dir, variables)
                status = "PASS" if summary.get("success") else "FAIL"
                return CheckResult(
                    table=self.table_cfg.name,
                    check_type="ge_expectations",
                    status=status,
                    details={
                        "mode": "checkpoint",
                        "failed": summary.get("failed"),
                        "failures": summary.get("failures"),
                    },
                )
            except Exception as e:
                log("ge.checkpoint.error", level="ERROR", error=str(e))
                return CheckResult(
                    table=self.table_cfg.name,
                    check_type="ge_expectations",
                    status="FAIL",
                    details={"error": f"checkpoint_error: {e}"},
                )

        # Pandas (inline suite) mode
        suite = _collect_expectations_from_rules(self.check_cfg.rules or [])
        expectations = suite.get("expectations") or []
        if not expectations:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="ge_expectations",
                status="SKIP",
                details={"reason": "no_expectations_provided"},
            )

        # Build SQL
        sql = rule.get("query")
        if not sql:
            if side == "source":
                sql = self.source.render_select_sql(self.table_cfg.source)
            elif side == "target":
                sql = self.target.render_select_sql(self.table_cfg.target)
            else:
                raise ValueError("ge_expectations 'on' must be 'source' or 'target'")

        # Fetch DataFrame
        try:
            df = (self.source if side == "source" else self.target).fetch_df(
                f"SELECT * FROM ({sql}) q LIMIT {limit}"
            )
        except Exception as e:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="ge_expectations",
                status="FAIL",
                details={"error": f"fetch_df_error: {e}"},
            )

        # Execute expectations
        try:
            summary = _pandas_expectations_runner(df, expectations)
            status = "PASS" if summary["failed"] == 0 else "FAIL"
            return CheckResult(
                table=self.table_cfg.name,
                check_type="ge_expectations",
                status=status,
                details={
                    "mode": "pandas",
                    "total": summary["total"],
                    "passed": summary["passed"],
                    "failed": summary["failed"],
                    "failures": summary["failures"],
                },
            )
        except Exception as e:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="ge_expectations",
                status="FAIL",
                details={"error": f"ge_runner_error: {e}"},
            )
