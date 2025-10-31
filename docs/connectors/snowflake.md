# Snowflake Connector

Module: `src/connectors/snowflake.py`

Capabilities

- SQL via SQLAlchemy (requires `snowflake-sqlalchemy`)
- `render_select_sql` from `QueryCfg` or verbatim `query`
- Deterministic hashing via MD5/SHA2 with HEX_ENCODE
- `information_schema_columns` implemented

URI

- SQLAlchemy DSN for Snowflake. Ensure driver is installed and URI valid.

Hashing (`HashingCfg`)

- Token: `COALESCE(TO_VARCHAR(col), '<null_token>')` with case folding
- `double_md5`: md5 of concatenated per‑token md5 hex
- `md5_row`: md5 of concatenated tokens
- `sha256_row`: sha256 of concatenated tokens

Notes

- If driver not installed, connector raises at init or on execution.

