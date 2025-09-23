"""
JoinRowDiff check:
- Aligns source/target columns to canonical names using mapping (include_map, table.column_map, or pairwise include_source/include_target).
- Fetches aligned dataframes (limited by max_rows_preview) including join keys and compare columns.
- Performs outer-join in-memory (pandas) to classify:
    * missing_on_target (present in source only)
    * extra_on_target   (present in target only)
    * mismatched_cells  (keys present on both sides but different values with optional tolerances)
- Supports:
    * include / include_map / include_source+include_target (same rules as hash_diff)
    * column_whitelist / column_blacklist (on canonical)
    * numeric tolerance: tolerance_abs / tolerance_pct applied per column
    * top_n preview for alerts
- For very large datasets, prefer planner partitions to fan-out comparisons.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.compiler.schema import ColumnMapEntry
from src.utils.sql import build_aligned_select
from src.runtime.registry import register_check


@dataclass
class Tolerance:
    abs: Optional[float] = None
    pct: Optional[float] = None

@register_check("join_rowdiff")
class JoinRowDiffCheck(BaseCheck):
    def _build_alignment(self) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
        """
        Resolve canonical compare columns and per-side projections.
        Returns (canonical_columns, source_projections, target_projections).
        """
        tcfg = self.table_cfg
        ccfg = self.check_cfg

        # Highest priority: explicit include_map
        if ccfg.include_map:
            canonical = list(ccfg.include_map.keys())
            s_proj = {k: ccfg.include_map[k].source for k in canonical}
            t_proj = {k: ccfg.include_map[k].target for k in canonical}
            return canonical, s_proj, t_proj

        # Table-level column_map limited to check.include
        if tcfg.column_map and ccfg.include:
            missing = [c for c in ccfg.include if c not in tcfg.column_map]
            if missing:
                raise ValueError(f"Missing columns in table.column_map: {missing}")
            canonical = list(ccfg.include)
            s_proj = {c: tcfg.column_map[c].source for c in canonical}
            t_proj = {c: tcfg.column_map[c].target for c in canonical}
            return canonical, s_proj, t_proj

        # Pairwise include_source + include_target
        if ccfg.include_source and ccfg.include_target:
            if len(ccfg.include_source) != len(ccfg.include_target):
                raise ValueError("include_source and include_target must have the same length")
            if ccfg.include and len(ccfg.include) == len(ccfg.include_source):
                canonical = list(ccfg.include)
            else:
                canonical = list(ccfg.include_source)
            s_proj = {canon: s for canon, s in zip(canonical, ccfg.include_source)}
            t_proj = {canon: t for canon, t in zip(canonical, ccfg.include_target)}
            return canonical, s_proj, t_proj

        # Identical names
        if ccfg.include:
            canonical = list(ccfg.include)
            s_proj = {c: c for c in canonical}
            t_proj = {c: c for c in canonical}
            return canonical, s_proj, t_proj

        raise ValueError("join_rowdiff requires include/column mapping; none provided")

    def _resolve_tolerances(self) -> Dict[str, Tolerance]:
        """
        Build a per-column tolerance map from check config.
        For simplicity, apply same tolerance_abs/pct to all columns if provided,
        but allow column-specific override via rules: [{col: 'amount', tolerance_abs: 0.01, tolerance_pct: 0.1}, ...]
        """
        tol_all = Tolerance(abs=self.check_cfg.tolerance_abs, pct=self.check_cfg.tolerance_pct)
        per_col: Dict[str, Tolerance] = {}
        if self.check_cfg.rules:
            for r in self.check_cfg.rules:
                col = r.get("col") or r.get("column")
                if not col:
                    continue
                per_col[col] = Tolerance(abs=r.get("tolerance_abs"), pct=r.get("tolerance_pct"))
        per_col["_default"] = tol_all
        return per_col

    def _compare_cell(self, left: Any, right: Any, tol: Tolerance) -> bool:
        """
        Return True if values are considered equal given tolerance; otherwise False.
        - For numerics: apply abs or pct tolerance if provided.
        - For strings: direct equality.
        - For NaNs/None: treat None == None as equal.
        """
        # Normalize NaNs
        if pd.isna(left) and pd.isna(right):
            return True
        if pd.isna(left) or pd.isna(right):
            return False

        # Try numeric comparison
        try:
            lf = float(left)
            rf = float(right)
            diff = abs(lf - rf)
            if tol.abs is not None and diff <= tol.abs:
                return True
            if tol.pct is not None:
                base = max(abs(rf), 1e-12)
                if (diff / base) * 100.0 <= tol.pct:
                    return True
            return lf == rf
        except Exception:
            # Fallback to exact equality for non-numeric types
            return left == right

    def run(self) -> CheckResult:
        # Build base selects
        base_s_sql = self.source.render_select_sql(self.table_cfg.source)
        base_t_sql = self.target.render_select_sql(self.table_cfg.target)

        # Build aligned compare columns
        canonical, s_proj, t_proj = self._build_alignment()

        # Build join keys (source/target expressions as provided)
        jk_src = list(self.table_cfg.join_keys.get("source", []))
        jk_tgt = list(self.table_cfg.join_keys.get("target", []))
        if len(jk_src) != len(jk_tgt):
            raise ValueError("join_keys.source and join_keys.target must have the same length")

        # Construct aligned projections including join keys with canonical names k1..kn
        s_all = {f"k{i+1}": e for i, e in enumerate(jk_src)}
        t_all = {f"k{i+1}": e for i, e in enumerate(jk_tgt)}
        for c in canonical:
            s_all[c] = s_proj[c]
            t_all[c] = t_proj[c]

        # Build aligned subqueries
        s_sql = build_aligned_select(base_s_sql, s_all)
        t_sql = build_aligned_select(base_t_sql, t_all)

        # Fetch dataframes (bounded by preview limit to avoid memory blowup)
        limit = int(self.vars_map.get("max_rows_preview", 1000))
        s_df = self.source.fetch_df(f"SELECT * FROM ({s_sql}) q LIMIT {limit}")
        t_df = self.target.fetch_df(f"SELECT * FROM ({t_sql}) q LIMIT {limit}")

        # Merge on join keys
        key_cols = [f"k{i+1}" for i in range(len(jk_src))]
        merged = s_df.merge(t_df, on=key_cols, how="outer", suffixes=("_s", "_t"), indicator=True)

        missing_on_t = merged[merged["_merge"] == "left_only"][key_cols].head(limit)
        extra_on_t = merged[merged["_merge"] == "right_only"][key_cols].head(limit)

        # Compare cell-by-cell where keys exist on both sides
        both = merged[merged["_merge"] == "both"].copy()

        # Apply whitelist/blacklist on canonical compare columns
        whitelist = set(canonical)
        if self.check_cfg.include:
            whitelist = whitelist.intersection(set(self.check_cfg.include))
        if self.check_cfg.exclude:
            whitelist = whitelist.difference(set(self.check_cfg.exclude))

        tol_map = self._resolve_tolerances()

        diffs: List[Dict[str, Any]] = []
        for _, row in both.iterrows():
            row_diffs = {}
            for c in whitelist:
                ls = row.get(f"{c}_s")
                rs = row.get(f"{c}_t")
                tol = tol_map.get(c, tol_map.get("_default", Tolerance()))
                if not self._compare_cell(ls, rs, tol):
                    row_diffs[c] = {"source": ls, "target": rs}
            if row_diffs:
                key_tuple = tuple(row[k] for k in key_cols)
                diffs.append({"keys": key_tuple, "cells": row_diffs})
                if len(diffs) >= limit:
                    break

        status = "PASS" if (missing_on_t.empty and extra_on_t.empty and not diffs) else "FAIL"
        return CheckResult(
            table=self.table_cfg.name,
            check_type="join_rowdiff",
            status=status,
            details={
                "missing_on_target": missing_on_t.to_dict(orient="records"),
                "extra_on_target": extra_on_t.to_dict(orient="records"),
                "mismatch_sample": diffs[:limit],
                "mismatch_total_estimate": len(diffs),
                "keys": key_cols,
                "canonical": canonical,
            },
        )
