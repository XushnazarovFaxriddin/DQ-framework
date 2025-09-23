"""Helpers for resolving secrets from environment variables."""

from __future__ import annotations

import os


def env_or_raise(key: str) -> str:
    value = os.getenv(key)
    if value is None or value == "":
        raise EnvironmentError(f"Environment variable '{key}' is required")
    return value


def env_or_default(key: str, default: str) -> str:
    value = os.getenv(key)
    return value if value not in {None, ""} else default
