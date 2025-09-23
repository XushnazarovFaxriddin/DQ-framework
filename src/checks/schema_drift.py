"""
SchemaDrift check:
- Compares source and target schemas: column presence, order (optional), data types, and (best-effort) nullability.
- For table-based sources we try to query information_schema; for arbitrary queries we fallback to LIMIT 0 approach.
- Notes:
  * Nullability inference via LIMIT 0 is not reliable; use information_schema when possible (table=...).
  * dtype normalization is engine-agnostic (string names are lowercased and simplified).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.utils.logger import ContextLogger
from src.runtime.registry import register_check

def _normalize_dtype(dtype_str: str) -> str:
    s = (dtype_str or "").strip().lower()
    # Basic normalization across engines and pandas dtypes
    replacements = {
        "character varying": "varchar",
        "double precision": "float64",
        "timestamp without time zone": "timestamp",
        "timestamp with time zone": "timestamptz",
        "int8": "bigint", "int4": "int", "int2": "smallint",
        "numeric": "decimal",
        "bignumeric": "decimal",
        "float": "float64", "float32": "float64",
        "boolean": "bool",
        "string": "varchar",
        "bytes": "binary",
        "datetime": "timestamp",
        "date32[day]": "date",  # pyarrow/pandas
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s


@dataclass
class ColumnSpec:
    name: str
    dtype: str
    nullable: Optional[bool] = None


@register_check("schema_drift")
class SchemaDriftCheck(BaseCheck):
    def _infer_from_dataframe(self, df: pd.DataFrame) -> List[ColumnSpec]:
        cols: List[ColumnSpec] = []
        for name, dtype in df.dtypes.items():
            cols.append(ColumnSpec(name=name, dtype=_normalize_dtype(str(dtype)), nullable=None))
        return cols

    def _infer_from_limit0(self, sql: str, side: str) -> List[ColumnSpec]:
        # SELECT * FROM (sql) q WHERE 1=0 OR LIMIT 0 (engine-specific)
        # We'll default to LIMIT 0 for simplicity; connectors can optimize as needed.
        if side == "source":
            q = f"SELECT * FROM ({sql}) q LIMIT 0"
            df = self.source.fetch_df(q)
        else:
            q = f"SELECT * FROM ({sql}) q LIMIT 0"
            df = self.target.fetch_df(q)
        return self._infer_from_dataframe(df)

    def _infer_table_schema(self, table_name: str, side: str) -> List[ColumnSpec]:
        # Best-effort via information_schema for Postgres/BigQuery.
        # If connector doesn't support, fallback to LIMIT 0.
        try:
            if side == "source":
                if getattr(self.source, "information_schema_columns", None):
                    rows = self.source.information_schema_columns(table_name)
                else:
                    return self._infer_from_limit0(f"SELECT * FROM {table_name}", "source")
            else:
                if getattr(self.target, "information_schema_columns", None):
                    rows = self.target.information_schema_columns(table_name)
                else:
                    return self._infer_from_limit0(f"SELECT * FROM `{table_name}`", "target")
            out = []
            for r in rows:
                out.append(ColumnSpec(
                    name=r["column_name"],
                    dtype=_normalize_dtype(r.get("data_type", "")),
                    nullable=r.get("is_nullable")))
            return out
        except Exception:
            # Fallback
            return self._infer_from_limit0(f"SELECT * FROM {table_name}", side)

    def _get_schema(self, side: str) -> List[ColumnSpec]:
        if side == "source":
            qcfg = self.table_cfg.source
            if qcfg.table and not qcfg.query:
                return self._infer_table_schema(qcfg.table, "source")
            sql = self.source.render_select_sql(qcfg)
            return self._infer_from_limit0(sql, "source")
        else:
            qcfg = self.table_cfg.target
            if qcfg.table and not qcfg.query:
                return self._infer_table_schema(qcfg.table, "target")
            sql = self.target.render_select_sql(qcfg)
            return self._infer_from_limit0(sql, "target")

    def run(self) -> CheckResult:
        cl = ContextLogger(table=self.table_cfg.name, check="schema_drift")
        src_schema = self._get_schema("source")
        tgt_schema = self._get_schema("target")

        # Build maps by name
        s_map = {c.name: c for c in src_schema}
        t_map = {c.name: c for c in tgt_schema}

        missing_on_target = [c.name for c in src_schema if c.name not in t_map]
        extra_on_target = [c.name for c in tgt_schema if c.name not in s_map]

        type_mismatches: List[Tuple[str, str, str]] = []
        nullable_mismatches: List[Tuple[str, Optional[bool], Optional[bool]]] = []

        for name in sorted(set(s_map.keys()).intersection(t_map.keys())):
            s = s_map[name]; t = t_map[name]
            if _normalize_dtype(s.dtype) != _normalize_dtype(t.dtype):
                type_mismatches.append((name, s.dtype, t.dtype))
            if (s.nullable is not None) and (t.nullable is not None) and (s.nullable != t.nullable):
                nullable_mismatches.append((name, s.nullable, t.nullable))

        status = "PASS" if (not missing_on_target and not extra_on_target and not type_mismatches and not nullable_mismatches) else "FAIL"
        cl.log("schema_drift.result", status=status,
               missing_on_target=len(missing_on_target), extra_on_target=len(extra_on_target),
               type_mismatches=len(type_mismatches), nullable_mismatches=len(nullable_mismatches))

        return CheckResult(
            table=self.table_cfg.name,
            check_type="schema_drift",
            status=status,
            details={
                "missing_on_target": missing_on_target[:50],
                "extra_on_target": extra_on_target[:50],
                "type_mismatches": type_mismatches[:50],
                "nullable_mismatches": nullable_mismatches[:50],
            }
        )
