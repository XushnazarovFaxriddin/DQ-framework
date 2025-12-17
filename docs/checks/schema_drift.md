# Schema Drift

Purpose: detect differences in schema between source and target.

How it works (`src/checks/schema_drift.py`):

- Infers columns (name, dtype, nullable) from information schema when available, or via `SELECT * FROM (...) WHERE 1=0`.
- Compares presence (missing/extra), data types (normalized), and nullability (best‑effort).
- Optional `expected_columns` to enforce an expected set.
- Case sensitivity can be toggled.

Config fields

- `type: schema_drift`
- `case_sensitive: false|true` (default false)
- `expected_columns: [ name1, name2, ... ]` (optional)

Example

```yaml
- type: schema_drift
  case_sensitive: false
```

Details output (truncated)

```
details: {
  case_sensitive: <bool>,
  missing_on_target: [ ... ],
  extra_on_target: [ ... ],
  nullable_mismatches: [ [col, src_nullable, tgt_nullable], ... ],
  expected_mismatches: [ ... ]
}
```

Status

- FAIL if any difference detected; otherwise PASS

