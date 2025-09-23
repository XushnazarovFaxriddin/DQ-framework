"""Runtime context creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.compiler.schema import ConfigModel
from src.connectors.factory import build_connector_pair
from src.utils.logger import log
from src.utils.secrets import env_or_raise


@dataclass
class RunContext:
    env: Optional[str]
    run_label: Optional[str]
    source_uri: str
    target_uri: str
    source: object
    target: object
    engines: tuple[str, str]


def build_run_context(cfg: ConfigModel, vars_map: dict) -> RunContext:
    env = vars_map.get("env")
    run_label = vars_map.get("run_label")

    source_uri = env_or_raise(cfg.connections.source_env_var)
    target_uri = env_or_raise(cfg.connections.target_env_var)

    source, target, engines = build_connector_pair(
        source_uri,
        target_uri,
        source_declared=cfg.connections.source_type,
        target_declared=cfg.connections.target_type,
    )

    declared_src = cfg.connections.source_type or "(unspecified)"
    declared_tgt = cfg.connections.target_type or "(unspecified)"

    log(
        "context.connections",
        env=env,
        run_label=run_label,
        source_env_var=cfg.connections.source_env_var,
        target_env_var=cfg.connections.target_env_var,
        declared_source_type=declared_src,
        declared_target_type=declared_tgt,
        actual_source_engine=engines[0],
        actual_target_engine=engines[1],
    )

    if cfg.connections.source_type and cfg.connections.source_type != engines[0]:
        log(
            "context.engine.mismatch",
            level="WARNING",
            side="source",
            declared=cfg.connections.source_type,
            actual=engines[0],
        )
    if cfg.connections.target_type and cfg.connections.target_type != engines[1]:
        log(
            "context.engine.mismatch",
            level="WARNING",
            side="target",
            declared=cfg.connections.target_type,
            actual=engines[1],
        )

    return RunContext(
        env=env,
        run_label=run_label,
        source_uri=source_uri,
        target_uri=target_uri,
        source=source,
        target=target,
        engines=engines,
    )
