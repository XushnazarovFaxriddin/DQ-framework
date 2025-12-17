# Domain

Purpose: validate values of a single column on one side (source or target).

How it works (`src/checks/domain.py`):

- Renders base query for the selected side (`'on': source|target`)
- Builds an invalid predicate from rules (allowed/excluded, regex, ranges)
- Computes `invalid_count`, `total_count`, and `invalid_pct`
- PASS if within configured tolerances; otherwise FAIL

Config fields

- `type: domain`
- `'on': source|target` (default: source)  [YAML: quote the key `'on'`]
- `column` (or `col`): column to validate
- Allowed / excluded values:
  - `allowed_values: [...]` or `include_values: [...]`
  - `exclude_values: [...]` (supports `null` to denote nulls)
- Regex: `regex: <pattern>` (engine‑specific)
- Range: `min`, `max` (numeric/date)
- Tolerance: `tolerance_abs`, `tolerance_pct`

Engine‑specific regex behavior

- BigQuery, Snowflake: `NOT REGEXP_CONTAINS(CAST(col AS STRING), r'<pattern>')`
- Postgres: `NOT (col ~ '<pattern>')`
- Oracle, MSSQL: `NOT REGEXP_LIKE(col, '<pattern>')`
- Other engines: regex ignored with a neutral clause

Examples

```yaml
# Not null on target
- type: domain
  'on': target
  column: email
  exclude_values: [null]

# Allowed set with regex and tolerance on source
- type: domain
  'on': source
  column: status
  allowed_values: ["new", "open", "closed"]
  regex: "^(new|open|closed)$"
  tolerance_pct: 0.5
```

Details output (dynamic)

```
details: {
  column, on, invalid_count, invalid_pct, total_count,
  allowed_values, excluded_values, regex, range, tolerance
}
```

Notes

- Always quote the key `'on'` in YAML to avoid YAML 1.1 boolean parsing issues. See Reference → YAML Quoting Rules.

