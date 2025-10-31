# YAML Quoting Rules (Important)

This project uses PyYAML (YAML 1.1 semantics). YAML 1.1 treats certain bare words as booleans (e.g., `on`, `off`, `yes`, `no`). As a result, using `on` as an unquoted key in a mapping can produce unexpected behavior (the key becomes a boolean `true` rather than the string `'on'`).

When you need to use the key `on` in check configurations (to select `source` or `target`), always quote the key:

Do:

```
- type: domain
  'on': source
  column: email
```

Donâ€™t:

```
- type: domain
  on: source   # may be parsed as boolean key in YAML 1.1
```

Applies to checks that accept an `on` key:

- Domain (`docs/checks/domain.md`)
- Freshness (`docs/checks/freshness.md`)
- Custom SQL (singleâ€‘mode) (`docs/checks/custom_sql.md`)
- Great Expectations adapter (`docs/checks/expectations_ge.md`)
- Soda adapter (`docs/checks/expectations_soda.md`)

General guidance:

- Quote suspicious scalars when used as keys: `'on'`, `'off'`, `'yes'`, `'no'`.
- For values, quoting is optional unless your engine requires a specific casing/format.


