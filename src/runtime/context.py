"""
Runtime context:
- Resolve env variables to connection URIs
- Build connector instances via factory
- Keep run-scoped metadata (env, run_label, engines)
"""

from dataclasses import dataclass
from typing import Optional

from src.utils.secrets import env_or_raise
from src.utils.logger import log
from src.connectors.factory import build_connector_pair
from src.compiler.schema import ConfigModel


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
    """
    Build RunContext by reading URIs from env vars defined in config.connections.
    Then create connector pair (source, target) based on URIs.
    """
    env = vars_map.get("env")
    run_label = vars_map.get("run_label")

    src_uri = env_or_raise(cfg.connections.source_env_var)
    tgt_uri = env_or_raise(cfg.connections.target_env_var)

    source, target, engines = build_connector_pair(src_uri, tgt_uri)

    log("context.built",
        env=env,
        run_label=run_label,
        source_env_var=cfg.connections.source_env_var,
        target_env_var=cfg.connections.target_env_var,
        source_engine=engines[0],
        target_engine=engines[1])

    return RunContext(
        env=env,
        run_label=run_label,
        source_uri=src_uri,
        target_uri=tgt_uri,
        source=source,
        target=target,
        engines=engines
    )