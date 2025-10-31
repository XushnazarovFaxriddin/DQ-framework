# Hashing & Parity

Purpose: produce deterministic per‑row hashes across heterogeneous engines for value parity checks (`hash_diff`). Defined by `HashingCfg` (`src/compiler/schema.py`).

Config fields

- `algorithm`: `double_md5` (default) | `md5_row` | `sha256_row`
- `null_token`: replacement for NULLs prior to hashing
- `delimiter`: token separator in row concatenation
- `case`: `none` | `lower` | `upper` normalization per token

Algorithms

- `double_md5`: MD5 of the concatenation of per‑column MD5 hex tokens.
- `md5_row`: MD5 of the concatenated normalized tokens.
- `sha256_row`: SHA256 similarly; only supported where connectors implement it.

Connector support highlights

- Postgres: `md5` + `pgcrypto` for sha256; final output lower‑cased.
- BigQuery: `MD5`/`SHA256` with `LOWER(TO_HEX(...))`.
- Oracle: `STANDARD_HASH(..., 'MD5'|'SHA256')` lower‑cased.
- MSSQL: `HASHBYTES('MD5'|'SHA2_256')` with `LOWER(CONVERT(..., 2))`.
- Snowflake: MD5/SHA2 with `HEX_ENCODE`, lower‑cased.
- CSV/GCS (DuckDB): md5 via `digest` or custom UDF; `sha256_row` not supported in CSV/GCS connectors.

Usage (YAML)

```
defaults:
  hashing: { algorithm: double_md5, null_token: "", delimiter: "|", case: upper }
```

Notes

- Ensure consistent hashing policy across connectors compared.
- Canonical column alignment ensures tokens match by position.

