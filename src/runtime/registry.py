"""
Global registries for connectors, checks, and alert backends.
Provides decorator helpers to register plugins in a uniform way.
"""

from typing import Callable, Dict, Optional, Type, Any

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
