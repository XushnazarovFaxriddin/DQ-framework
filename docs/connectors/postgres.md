# Postgres Connector

Module: `src/connectors/postgres.py`

Capabilities

- SQL via SQLAlchemy engine
- `render_select_sql` from `QueryCfg` or verbatim `query`
- Deterministic hashing parity (MD5/SHA256 via pgcrypto)
- Fetch helpers: `fetch_df`, `fetch_scalar`, `fetch_column`

URI

- Standard SQLAlchemy DSN, e.g. `postgres://user:pass@host:5432/db`

Hashing (`HashingCfg`)

- Token: `COALESCE(col::text, '<null_token>')` with optional lower/upper
- `double_md5`: `lower(md5(concat_ws(delim, md5(token1), ...)))`
- `md5_row`: `lower(md5(concat_ws(delim, token1, ...)))`
- `sha256_row`: `lower(encode(digest(concat_ws(...), 'sha256'), 'hex'))`

