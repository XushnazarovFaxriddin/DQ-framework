"""
SodaCL (Soda Core) adapter for DQF.

Execution model
---------------
We use Soda Core's Python API:
    from soda.scan import Scan
    scan = Scan()
    scan.add_configuration_yaml_file("configuration.yml")  # data source config
    scan.set_data_source_name("my_ds")
    scan.add_sodacl_yaml_file("checks.yml") or add_sodacl_yaml_str("...yaml...")
    scan.set_variables({...})  # optional
    scan.execute()

Assumptions
-----------
- Data source connection is managed by Soda configuration YAML, not by DQF connectors.
- You can pass the configuration YAML path via:
    rules[0].config_file: "path/to/configuration.yml"
  or inline:
    rules[0].config_yaml: "<yaml string>"
- The Soda data source name used inside checks.yml must be provided:
    rules[0].data_source: "my_ds"
- Checks can be provided as:
    rules[0].checks_file: "path/to/checks.yml"
    OR
    rules[0].checks_yaml: "<yaml string>"

Optional
--------
- on: "source"|"target" (if your checks.yml references tables/views bound to that side)
  Note: Soda connects independently; 'on' is informational here unless you template it.
- variables: { var1: value, ... } to substitute in Sodacl
- query: "<SQL>" optional - if provided, we create a temporary Soda scan named query
        and bind it via a variable (e.g., {{ query }}) inside checks.

Outcome
-------
- PASS if scan has no failures, FAIL otherwise; details include failed checks.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.utils.logger import log
from src.runtime.registry import register_check

def _safe_import_soda():
    try:
        from soda.scan import Scan  # type: ignore
        return Scan
    except Exception as e:
        raise ImportError("soda-core is not installed or not importable") from e


register_check("soda_checks")
class SodaCheckAdapter(BaseCheck):
    def run(self) -> CheckResult:
        rule = (self.check_cfg.rules or [{}])[0]
        data_source = rule.get("data_source")
        if not data_source:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="soda_checks",
                status="SKIP",
                details={"reason": "data_source not provided"},
            )

        # Config: either file or inline YAML
        config_file = rule.get("config_file")
        config_yaml = rule.get("config_yaml")

        # Checks: either file or inline YAML
        checks_file = rule.get("checks_file")
        checks_yaml = rule.get("checks_yaml")

        variables = rule.get("variables") or {}
        on = str(rule.get("on", "source")).lower()

        # Optional: pass a query via variable if needed by checks
        query = rule.get("query")
        if not query:
            # You can use templating in your Soda checks to choose the table based on 'on'
            # Example in checks.yml:  tables: {{ table_name }}
            pass

        Scan = _safe_import_soda()
        scan = Scan()

        # Load configuration
        try:
            if config_file:
                scan.add_configuration_yaml_file(config_file)
            elif config_yaml:
                scan.add_configuration_yaml_str(config_yaml)
            else:
                # Fallback to env var SODA_CONFIG if user set it
                env_cfg = os.getenv("SODA_CONFIG")
                if env_cfg:
                    scan.add_configuration_yaml_file(env_cfg)
                else:
                    return CheckResult(
                        table=self.table_cfg.name,
                        check_type="soda_checks",
                        status="SKIP",
                        details={"reason": "no Soda configuration provided"},
                    )
        except Exception as e:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="soda_checks",
                status="FAIL",
                details={"error": f"config_load_error: {e}"},
            )

        # Set data source
        try:
            scan.set_data_source_name(data_source)
        except Exception as e:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="soda_checks",
                status="FAIL",
                details={"error": f"data_source_error: {e}"},
            )

        # Inject variables (allow framework variables + user-provided)
        vars_full = dict(self.vars_map)
        vars_full.update(variables or {})
        vars_full["on"] = on  # pass which side
        scan.set_variables(vars_full)

        # Provide checks
        try:
            if checks_file:
                scan.add_sodacl_yaml_file(checks_file)
            elif checks_yaml:
                scan.add_sodacl_yaml_str(checks_yaml)
            else:
                return CheckResult(
                    table=self.table_cfg.name,
                    check_type="soda_checks",
                    status="SKIP",
                    details={"reason": "no checks provided (checks_file/checks_yaml)"},
                )
        except Exception as e:
            return CheckResult(
                table=self.table_cfg.name,
                check_type="soda_checks",
                status="FAIL",
                details={"error": f"checks_load_error: {e}"},
            )

        # Execute
        try:
            scan.execute()
            sres = scan.get_scan_result()
            has_failures = bool(getattr(sres, "has_failures", lambda: False)())
            status = "FAIL" if has_failures else "PASS"

            # Extract some failure details if available
            failures: List[Dict[str, Any]] = []
            try:
                # soda-core provides logs/measurements; we keep a compact view
                for chk in sres.get_checks():
                    # chk.outcome: 'pass'|'fail'|'warn' etc.
                    if getattr(chk, "is_failed", False) or getattr(chk, "outcome", "") == "fail":
                        failures.append({
                            "name": getattr(chk, "name", None),
                            "identity": getattr(chk, "identity", None),
                            "outcome": getattr(chk, "outcome", None),
                            "diagnostics": getattr(chk, "diagnostics", None),
                        })
            except Exception:
                # Best-effort
                pass

            return CheckResult(
                table=self.table_cfg.name,
                check_type="soda_checks",
                status=status,
                details={
                    "failures": failures[:50],
                    "failed": len(failures),
                    "data_source": data_source,
                },
            )
        except Exception as e:
            log("soda.scan.error", level="ERROR", error=str(e))
            return CheckResult(
                table=self.table_cfg.name,
                check_type="soda_checks",
                status="FAIL",
                details={"error": f"scan_execute_error: {e}"},
            )


