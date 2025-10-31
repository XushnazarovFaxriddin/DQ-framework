# Troubleshooting

Common issues and fixes.

YAML quoting for 'on'

- Symptom: checks ignoring the selected side or throwing unexpected key errors.
- Fix: YAML 1.1 treats `on` as boolean when unquoted. Always quote `'on'`.

BigQuery auth

- Symptom: `403` or `unauthorized` when running BigQuery checks.
- Fix: ensure ADC is set (`GOOGLE_APPLICATION_CREDENTIALS`), or run `gcloud auth application-default login`.

MSSQL connectivity

- Symptom: connection failures or driver errors.
- Fix: verify `pymssql` and FreeTDS configuration; confirm DSN `mssql://user:pass@host:port/db`.

Oracle client

- Symptom: `oracledb` import or connectivity issues.
- Fix: thin mode should work by default; thick mode needs Instant Client libraries and proper `LD_LIBRARY_PATH`/PATH.

Hash parity mismatches

- Symptom: `hash_diff` fails unexpectedly.
- Fix: align columns precisely (prefer `include_map`), confirm identical hashing policy across connectors, normalize case via `defaults.hashing.case`.

Regex differences

- Symptom: regex behavior differs across engines in `domain`.
- Fix: follow engine‑specific notes; if regex unsupported, the adapter uses a neutral predicate.

