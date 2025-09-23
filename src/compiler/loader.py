import importlib.util
import os
import re
from typing import Any, Dict

import yaml

from ..utils.logger import log


_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate_env(text: str) -> str:
    """
    Replace ${VAR} occurrences with environment variable values.
    Missing variables are left as-is to avoid surprising defaults;
    upstream validation can enforce required envs where needed.
    """
    def repl(m):
        var = m.group(1)
        return os.getenv(var, m.group(0))
    return _ENV_REF.sub(repl, text)


def _load_yaml(path: str) -> Dict[str, Any]:
    """
    Load YAML config with environment interpolation.
    Jinja is intentionally not hard-wired here to keep YAML simple;
    if templating is required, it can be layered in the planner.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    rendered = _interpolate_env(raw)
    try:
        data = yaml.safe_load(rendered) or {}
        if not isinstance(data, dict):
            raise ValueError("Top-level YAML must be a mapping")
        return data
    except Exception as e:
        log("config.load.yaml.error", path=path, error=str(e), level="ERROR")
        raise


def _load_py(path: str, vars_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load a Python config module and execute its `build(vars)` factory.
    The module is not imported into sys.modules to reduce side-effects.
    """
    spec = importlib.util.spec_from_file_location("dqf_pyconfig", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create import spec for: {path}")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    except Exception as e:
        log("config.load.py.exec.error", path=path, error=str(e), level="ERROR")
        raise

    if not hasattr(mod, "build"):
        raise AttributeError(f"Python config must define a 'build(vars: dict) -> dict' function: {path}")

    try:
        data = mod.build(vars_map)  # type: ignore[attr-defined]
        if not isinstance(data, dict):
            raise TypeError("build(vars) must return a dict")
        return data
    except Exception as e:
        log("config.load.py.build.error", path=path, error=str(e), level="ERROR")
        raise


def load_config(args) -> Dict[str, Any]:
    """
    Public loader dispatch.
    Returns a raw python dict (later validated by pydantic schema).
    """
    path = args.config_file
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    if args.filetype == "yaml":
        log("config.load.yaml.start", path=path)
        cfg = _load_yaml(path)
        log("config.load.yaml.done", path=path)
        return cfg

    if args.filetype == "py":
        log("config.load.py.start", path=path)
        cfg = _load_py(path, args.vars)
        log("config.load.py.done", path=path)
        return cfg

    raise ValueError(f"Unsupported filetype: {args.filetype}")