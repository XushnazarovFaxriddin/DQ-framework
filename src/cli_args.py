import argparse
from typing import Dict, List


def _parse_kv_list(pairs: List[str] | None) -> Dict[str, str]:
    """
    Parse a list of key=value strings into a dictionary.
    Rejects malformed items to avoid silent misconfiguration.
    """
    out: Dict[str, str] = {}
    if not pairs:
        return out
    for kv in pairs:
        if "=" not in kv:
            raise ValueError(f"Invalid --vars item (expected key=value): {kv}")
        k, v = kv.split("=", 1)
        k = k.strip()
        if not k:
            raise ValueError(f"Empty key in --vars item: {kv}")
        out[k] = v
    return out


def parse_args(argv: List[str]):
    """
    Unified CLI parser:
      - Supports both '--vars key=v key2=v2' AND '--env prod --run_label 2025-09-09'
      - Keeps future-proof flags like concurrency and preview limits
    """
    p = argparse.ArgumentParser(
        prog="dqf",
        description="DQF — Config-driven, pluggable Data Quality Framework",
    )

    # Required
    p.add_argument("--config-file", required=True, help="Path to YAML or Python config file")
    p.add_argument("--filetype", required=True, choices=["yaml", "py"], help="Config type")

    # Two styles of variable passing
    p.add_argument("--vars", nargs="*", help="key=value pairs, e.g. --vars env=prod run_label=nightly_2025-09-09")
    p.add_argument("--env", help="Environment name (e.g., cert/prod)")
    p.add_argument("--run_label", help="Label for this run (e.g., nightly_2025-09-09)")

    # Execution controls
    p.add_argument("--concurrency", type=int, default=4, help="Max parallel tables to check")
    p.add_argument("--max_rows_preview", type=int, default=1000, help="Max preview rows for diffs/attachments")

    args = p.parse_args(argv)

    # Merge both styles into a single dictionary
    var_map = _parse_kv_list(args.vars)
    if args.env:
        var_map["env"] = args.env
    if args.run_label:
        var_map["run_label"] = args.run_label
    args.vars = var_map

    return args
