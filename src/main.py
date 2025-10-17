"""CLI entrypoint for DQF."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict
from dotenv import load_dotenv

from src.cli_args import parse_args
from src.compiler.loader import load_config
from src.compiler.normalizer import normalize_config
from src.compiler.planner import build_plan
from src.compiler.schema import ConfigModel
from src.render.summarize import summarize_run
from src.render.tabular import markdown_summary_table
from src.runtime.registry import register_all
from src.utils.logger import log


def _build_cli_overrides(parsed) -> Dict[str, Any]:
    return {
        "concurrency": parsed.concurrency,
        "concurrency_checks": parsed.concurrency_checks,
        "table_timeout_sec": parsed.table_timeout_sec,
        "check_timeout_sec": parsed.check_timeout_sec,
        "max_rows_preview": parsed.max_rows_preview,
    }


def main() -> None:
    load_dotenv()
    register_all()
    parsed = parse_args(sys.argv[1:])

    raw_cfg = load_config(parsed)
    model = ConfigModel.model_validate(raw_cfg)

    logging.basicConfig(level=logging.getLevelName("INFO"))

    cfg, runtime_vars = normalize_config(
        model,
        parsed.vars,
        alerts_override=parsed.alerts_override,
        cli_overrides=_build_cli_overrides(parsed),
    )

    log(
        "main.start",
        env=runtime_vars.get("env"),
        run_label=runtime_vars.get("run_label"),
    )

    plan = build_plan(cfg, runtime_vars)
    run_result = plan.run()

    summary = summarize_run(run_result)
    table_md = markdown_summary_table(run_result, max_rows=20)
    try:
        run_result_str = json.dumps(run_result, indent=4, default=str)
        logging.info(f"RUN RESULT: \n{run_result_str}")
    except:
        pass
    logging.info(f"\n{summary}")
    print()
    logging.info(f"\n{table_md}")

    exit_code = 0 if run_result.overall_status == "PASS" else 1
    log("main.finish", overall_status=run_result.overall_status)
    if exit_code > 0:
        raise Exception(f"Run failed with status: {run_result.overall_status}. Details: {summary}")
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()
