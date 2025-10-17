"""
Hash diff check with mapping-aware column alignment.

Priority to build alignment:
  1) check.include_map
  2) table.column_map restricted to check.include
  3) pairwise check.include_source + check.include_target (same length)
  4) check.include (assume identical names)
"""

from typing import Dict, List, Tuple

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.utils.sql import build_aligned_select, wrap_order_by, sanitize_identifier, wrap_order_by_limit
from src.runtime.registry import register_check


@register_check("hash_diff")
class HashDiffCheck(BaseCheck):
    def _build_alignment(self) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
        """
        Returns:
          - canonical list in order
          - source projections: {canonical: expr}
          - target projections: {canonical: expr}
        """
        tcfg = self.table_cfg
        ccfg = self.check_cfg

        # 1) include_map (highest priority)
        if ccfg.include_map:
            canonical = list(ccfg.include_map.keys())
            s_proj = {k: ccfg.include_map[k].source for k in canonical}
            t_proj = {k: ccfg.include_map[k].target for k in canonical}
            return canonical, s_proj, t_proj

        # 2) table-level column_map + include (canonical names)
        if tcfg.column_map and ccfg.include:
            missing = [c for c in ccfg.include if c not in tcfg.column_map]
            if missing:
                raise ValueError(f"Missing columns in table.column_map: {missing}")
            canonical = list(ccfg.include)
            s_proj = {c: tcfg.column_map[c].source for c in canonical}
            t_proj = {c: tcfg.column_map[c].target for c in canonical}
            return canonical, s_proj, t_proj

        # 3) pairwise include_source + include_target
        if ccfg.include_source and ccfg.include_target:
            if len(ccfg.include_source) != len(ccfg.include_target):
                raise ValueError(
                    "include_source and include_target must have the same length"
                )
            # Canonical names: prefer ccfg.include if given, else use source names
            if ccfg.include and len(ccfg.include) == len(ccfg.include_source):
                canonical = list(ccfg.include)
            else:
                canonical = list(ccfg.include_source)
            s_proj = {canon: s for canon, s in zip(canonical, ccfg.include_source)}
            t_proj = {canon: t for canon, t in zip(canonical, ccfg.include_target)}
            return canonical, s_proj, t_proj

        # 4) include only (identical names)
        if ccfg.include:
            canonical = list(ccfg.include)
            s_proj = {c: c for c in canonical}
            t_proj = {c: c for c in canonical}
            return canonical, s_proj, t_proj

        raise ValueError(
            "hash_diff requires at least one of: include_map, include (+table.column_map), include_source+include_target, or include"
        )

    def run(self) -> CheckResult:
        # Build base selects from source/target configs
        base_s_sql = self.source.render_select_sql(self.table_cfg.source)
        base_t_sql = self.target.render_select_sql(self.table_cfg.target)

        # Resolve alignment
        canonical, s_proj, t_proj = self._build_alignment()

        # Build aligned subqueries projecting canonical columns on both sides
        s_sql = build_aligned_select(base_s_sql, s_proj)
        t_sql = build_aligned_select(base_t_sql, t_proj)

        order_by_source = self.check_cfg.order_by_source
        order_by_target = self.check_cfg.order_by_target
        if not order_by_source and self.check_cfg.order_by:
            order_by_source = [
                sanitize_identifier(col) for col in self.check_cfg.order_by
            ]
        if not order_by_target and self.check_cfg.order_by:
            order_by_target = [
                sanitize_identifier(col) for col in self.check_cfg.order_by
            ]

        s_sql = wrap_order_by_limit(s_sql, order_by_source, None, engine=self.source.engine_name)
        t_sql = wrap_order_by_limit(t_sql, order_by_target, None, engine=self.target.engine_name)

        # Hash expressions over canonical column names (same on both sides)
        s_hash_expr = self.source.hash_expr(canonical, self.hashing)
        t_hash_expr = self.target.hash_expr(canonical, self.hashing)

        s_h_sql = f"SELECT {s_hash_expr} AS h FROM ({s_sql}) q"
        t_h_sql = f"SELECT {t_hash_expr} AS h FROM ({t_sql}) q"

        s_hashes = set(self.source.fetch_column(s_h_sql))
        t_hashes = set(self.target.fetch_column(t_h_sql))

        missing = list(s_hashes - t_hashes)
        extra = list(t_hashes - s_hashes)

        status = "PASS" if not missing and not extra else "FAIL"
        # Filter details dict to keep only non-empty/non-null fields
        details = {
            k: v
            for k, v in {
            "algorithm": self.hashing.algorithm,
            "canonical": canonical,
            "missing_count": len(missing),
            "extra_count": len(extra),
            # "missing_sample": missing[:10],
            # "extra_sample": extra[:10],
            }.items()
            if v not in (None, "", [], {})
        }

        return CheckResult(
            table=self.table_cfg.name,
            check_type="hash_diff",
            status=status,
            details=details,
        )
