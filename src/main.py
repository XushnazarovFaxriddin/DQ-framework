import sys
from src.cli_args import parse_args
from src.compiler.loader import load_config
from src.compiler.schema import ConfigModel
from src.compiler.normalizer import normalize_config
from src.compiler.planner import build_plan
from src.runtime.runner import run_planfrom 
from src.checks.registry import register_all_checks

def main(): 
    register_all_checks()
    args = parse_args(sys.argv[1:])
    raw = load_config(args)
    model = ConfigModel.model_validate(raw)        # pydantic validation
    cfg = normalize_config(model, args.vars)       # defaults, templating, merges
    plan = build_plan(cfg, args)                   # DAG-like exec plan
    result = run_planfrom(plan, args)
    code = 0 if result.overall_status == "PASS" else 1
    sys.exit(code)
