# MSSQL Connector

Module: `src/connectors/mssql.py`

Capabilities

- SQL via `pymssql`
- `render_select_sql` from `QueryCfg` or verbatim `query`
- Deterministic hashing parity via `HASHBYTES`
- `information_schema_columns` implemented

URI

- Custom scheme parsed manually: `mssql://user:password@host:port/database`

Hashing (`HashingCfg`)

- Token: `ISNULL(CAST(col AS NVARCHAR(MAX)), '<null_token>')` with lower/upper
- `double_md5`: per‑token MD5 hex then MD5 row, `LOWER(CONVERT(VARCHAR(32), HASHBYTES('MD5', ...), 2))`
- `md5_row`: `LOWER(CONVERT(VARCHAR(32), HASHBYTES('MD5', tokens), 2))`
- `sha256_row`: `LOWER(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', tokens), 2))`

