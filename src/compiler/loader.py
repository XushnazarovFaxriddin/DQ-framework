"""Configuration loader for YAML and Python sources."""

from __future__ import annotations

import importlib.util
import inspect
import os
import re
from typing import Any, Dict, Mapping

import yaml

from src.utils.logger import log

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate_env(text: str) -> str:
    """Replace ``${VAR}`` occurrences with environment variable values."""

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        return os.getenv(var, match.group(0))

    return _ENV_REF.sub(repl, text)


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read()
    rendered = _interpolate_env(raw)
    data = yaml.safe_load(rendered) or {}
    if not isinstance(data, Mapping):
        raise ValueError("Top-level YAML must be a mapping")
    return dict(data)


def _evaluate_python_payload(payload: Any, vars_map: Dict[str, Any]) -> Dict[str, Any]:
    if callable(payload):
        result = payload(vars_map)
        if isinstance(result, Mapping):
            return dict(result)
        raise TypeError("Python config callable must return a mapping")
    if isinstance(payload, Mapping):
        return dict(payload)
    raise TypeError("Python config must provide a mapping or callable returning one")


def _load_py(path: str, vars_map: Dict[str, Any]) -> Dict[str, Any]:
    spec = importlib.util.spec_from_file_location("dqf_pyconfig", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create import spec for: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - surfaced in tests
        log("config.load.py.exec.error", path=path, error=str(exc), level="ERROR")
        raise

    candidates: list[Any] = []
    if hasattr(module, "build"):
        candidates.append(getattr(module, "build"))
    if hasattr(module, "CONFIG"):
        candidates.append(getattr(module, "CONFIG"))

    if not candidates:
        raise AttributeError(
            "Python config must expose a 'build(vars)' callable or 'CONFIG' mapping/callable"
        )

    for candidate in candidates:
        try:
            payload = (
                candidate(vars_map) if inspect.isfunction(candidate) else candidate
            )
            return _evaluate_python_payload(payload, vars_map)
        except TypeError:
            # Candidate may be a callable without vars argument
            if callable(candidate):
                payload = candidate()
                return _evaluate_python_payload(payload, vars_map)
            raise
    raise RuntimeError("Unable to evaluate Python config payload")


def load_config(args: Any) -> Dict[str, Any]:
    path = args.config_file
    if "/" not in path and "\\" not in path:
        path = f"config/{args.filetype}/{path}.{args.filetype}"
    current_path = os.getcwd()
    path = os.path.join(current_path, path)
    if not os.path.exists(path):
        print(f"Config file not found: {path}")
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
