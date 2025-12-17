# Oracle Connector

Module: `src/connectors/oracle.py`

Capabilities

- SQL via SQLAlchemy engine
- `render_select_sql` from `QueryCfg` or verbatim `query`
- Deterministic hashing parity via `STANDARD_HASH`
- `information_schema_columns` via `ALL_TAB_COLUMNS`

URI

- SQLAlchemy DSN, e.g. `oracle+oracledb://user:pass@host:1521/service`

Hashing (`HashingCfg`)

- Token: `NVL(TO_CHAR(col), '<null_token>')` with lower/upper
- `double_md5`: `LOWER(STANDARD_HASH(CONCAT(md5_tokens...), 'MD5'))`
- `md5_row`: `LOWER(STANDARD_HASH(CONCAT(tokens...), 'MD5'))`
- `sha256_row`: `LOWER(STANDARD_HASH(CONCAT(tokens...), 'SHA256'))`

