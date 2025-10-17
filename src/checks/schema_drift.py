"""
SchemaDrift check (dynamic + case-sensitive option):
- Compares source and target schemas: column presence, order (optional), data types, and (best-effort) nullability.
- If check_cfg.expected_columns is provided, validate against those explicitly.
- Otherwise, only compare source vs target differences.
- Column name comparison is case-insensitive by default, but can be set to case-sensitive.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from src.checks.base import BaseCheck
from src.runtime.results import CheckResult
from src.utils.logger import ContextLogger
from src.runtime.registry import register_check


def _normalize_dtype(dtype_str: str) -> str:
    s = (dtype_str or "").strip().lower()
    replacements = {
        "character varying": "varchar",
        "double precision": "float64",
        "timestamp without time zone": "timestamp",
        "timestamp with time zone": "timestamptz",
        "int8": "bigint",
        "int4": "int",
        "int2": "smallint",
        "numeric": "decimal",
        "bignumeric": "decimal",
        "float": "float64",
        "float32": "float64",
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
        return [ColumnSpec(name=name, dtype=_normalize_dtype(str(dtype)), nullable=None) for name, dtype in df.dtypes.items()]

    def _infer_from_limit0(self, sql: str, side: str) -> List[ColumnSpec]:
        q = f"SELECT * FROM ({sql}) q WHERE 1=0"
        df = self.source.fetch_df(q) if side == "source" else self.target.fetch_df(q)
        return self._infer_from_dataframe(df)

    def _infer_table_schema(self, table_name: str, side: str) -> List[ColumnSpec]:
        try:
            rows = None
            if side == "source" and getattr(self.source, "information_schema_columns", None):
                rows = self.source.information_schema_columns(table_name)
            elif side == "target" and getattr(self.target, "information_schema_columns", None):
                rows = self.target.information_schema_columns(table_name)

            if rows is not None:
                return [
                    ColumnSpec(
                        name=r["column_name"],
                        dtype=_normalize_dtype(r.get("data_type", "")),
                        nullable=r.get("is_nullable"),
                    )
                    for r in rows
                ]

            return self._infer_from_limit0(f"SELECT * FROM {table_name}", side)
        except Exception:
            return self._infer_from_limit0(f"SELECT * FROM {table_name}", side)

    def _get_schema(self, side: str) -> List[ColumnSpec]:
        qcfg = self.table_cfg.source if side == "source" else self.table_cfg.target
        if qcfg.table and not qcfg.query:
            return self._infer_table_schema(qcfg.table, side)
        sql = self.source.render_select_sql(qcfg) if side == "source" else self.target.render_select_sql(qcfg)
        return self._infer_from_limit0(sql, side)

    def run(self) -> CheckResult:
        cl = ContextLogger(table=self.table_cfg.name, check="schema_drift")

        case_sensitive = getattr(self.check_cfg, "case_sensitive", False)

        src_schema = self._get_schema("source")
        tgt_schema = self._get_schema("target")

        # normalize keys based on case sensitivity
        def _key(name: str) -> str:
            return name if case_sensitive else name.lower()

        s_map = {_key(c.name): c for c in src_schema}
        t_map = {_key(c.name): c for c in tgt_schema}

        missing_on_target = [c.name for c in src_schema if _key(c.name) not in t_map]
        extra_on_target = [c.name for c in tgt_schema if _key(c.name) not in s_map]

        type_mismatches: List[Tuple[str, str, str]] = []
        nullable_mismatches: List[Tuple[str, Optional[bool], Optional[bool]]] = []

        for key in sorted(set(s_map.keys()).intersection(t_map.keys())):
            s = s_map[key]
            t = t_map[key]
            if _normalize_dtype(s.dtype) != _normalize_dtype(t.dtype):
                type_mismatches.append((s.name, s.dtype, t.dtype))
            if (s.nullable is not None) and (t.nullable is not None) and (s.nullable != t.nullable):
                nullable_mismatches.append((s.name, s.nullable, t.nullable))

        # Extra validation if expected_columns is provided
        expected_mismatches: List[str] = []
        if getattr(self.check_cfg, "expected_columns", None):
            expected_cols = set(
                [_key(c) for c in self.check_cfg.expected_columns]
            )
            for col in expected_cols:
                if col not in s_map or col not in t_map:
                    expected_mismatches.append(col)

        status = "PASS"
        if missing_on_target or extra_on_target or type_mismatches or nullable_mismatches or expected_mismatches:
            status = "FAIL"

        cl.log(
            "schema_drift.result",
            status=status,
            case_sensitive=case_sensitive,
            missing_on_target=len(missing_on_target),
            extra_on_target=len(extra_on_target),
            type_mismatches=len(type_mismatches),
            nullable_mismatches=len(nullable_mismatches),
            expected_mismatches=len(expected_mismatches),
        )

        details = {
            "case_sensitive": case_sensitive,
            "missing_on_target": missing_on_target[:1000],
            "extra_on_target": extra_on_target[:1000],
            #"type_mismatches": type_mismatches[:1000],
            "nullable_mismatches": nullable_mismatches[:1000],
            "expected_mismatches": expected_mismatches[:1000],
        }
        details = {k: v for k, v in details.items() if v not in (None, "", [], {})}

        return CheckResult(
            table=self.table_cfg.name,
            check_type="schema_drift",
            status=status,
            details=details,
        )
