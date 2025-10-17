"""
Global registries for connectors, checks, and alert backends.
Provides decorator helpers to register plugins in a uniform way.
"""

import importlib
import pkgutil
from typing import Callable, Dict, Optional, Type, Any

from src.utils.logger import log

# Registries
CONNECTORS: Dict[str, Type] = {}  # key: canonical engine name (e.g., "postgres")
CHECKS: Dict[str, Type] = {}  # key: check type (e.g., "row_count")
ALERTS: Dict[str, Callable[..., Any]] = {}  # key: "gchat" | "email" etc.


def register_connector(name: str):
    """
    Decorator to register a connector class under a canonical name.
    The connector must implement the BaseConnector interface.
    """

    def _wrap(cls: Type):
        CONNECTORS[name] = cls
        return cls

    return _wrap


def register_check(name: str):
    """
    Decorator to register a check class under a given type string.
    """

    def _wrap(cls: Type):
        CHECKS[name] = cls
        return cls

    return _wrap


def register_alert(name: str):
    """
    Decorator to register an alert sending function.
    """

    def _wrap(fn: Callable[..., Any]):
        ALERTS[name] = fn
        return fn

    return _wrap

# Auto-import utilities
def _import_all_submodules(package: str, target: str) -> None:
    """
    Import all submodules under a given package path.
    Example: package="src.checks", target="checks"
    """
    try:
        package_obj = importlib.import_module(package)
    except Exception as e:
        log(f"{target}.registry.import.error", level="ERROR", package=package, error=str(e))
        return

    package_path = getattr(package_obj, "__path__", None)
    if not package_path:
        return

    for _, name, ispkg in pkgutil.iter_modules(package_path):
        if name.startswith("_"):
            continue  # skip private modules
        module_path = f"{package}.{name}"
        try:
            importlib.import_module(module_path)
            log(f"{target}.registry.import.ok", module=module_path)
            if ispkg:
                _import_all_submodules(module_path, target)
        except Exception as e:
            log(f"{target}.registry.import.error", level="ERROR", module=module_path, error=str(e))


# Public registry loaders
def register_all_connectors() -> Dict[str, str]:
    log("connectors.registry.start")
    _import_all_submodules("src.connectors", "connectors")
    summary = {k: f"{v.__module__}.{v.__qualname__}" for k, v in CONNECTORS.items()}
    log("connectors.registry.done", registered=len(summary))
    return summary


def register_all_checks() -> Dict[str, str]:
    log("checks.registry.start")
    _import_all_submodules("src.checks", "checks")
    summary = {k: f"{v.__module__}.{v.__qualname__}" for k, v in CHECKS.items()}
    log("checks.registry.done", registered=len(summary))
    return summary

def register_all_alerts() -> Dict[str, str]:
    log("alerts.registry.start")
    _import_all_submodules("src.alerts", "alerts")
    summary = {k: getattr(v, "__name__", str(v)) for k, v in ALERTS.items()}
    log("alerts.registry.done", registered=len(summary))
    return summary

def register_all() -> Dict[str, Dict[str, str]]:
    log("registry.all.start")
    connectors = register_all_connectors()
    checks = register_all_checks()
    alerts = register_all_alerts()
    summary = {
        "connectors": connectors,
        "checks": checks,
        "alerts": alerts,
    }
    log("registry.all.done",
        connectors=len(connectors),
        checks=len(checks),
        alerts=len(alerts))
    return summary


# ---- Query helpers ----
def get_check(name: str) -> Optional[Type]:
    return CHECKS.get(name)


def list_checks() -> Dict[str, str]:
    """
    Return a mapping of check_name -> class_qualname for diagnostics.
    """
    return {k: f"{v.__module__}.{v.__qualname__}" for k, v in CHECKS.items()}


def get_connector(name: str) -> Optional[Type]:
    return CONNECTORS.get(name)


def list_connectors() -> Dict[str, str]:
    return {k: f"{v.__module__}.{v.__qualname__}" for k, v in CONNECTORS.items()}


def list_alerts() -> Dict[str, str]:
    return {k: getattr(v, "__name__", str(v)) for k, v in ALERTS.items()}
