# Results & Reporting

Outputs

- Logs: textual summary and markdown table in process output.
- Alerts: Google Chat (text/card) and Email (text + HTML + CSV attachments).
- Alerts surface "Mismatch CSV" URLs when `details["mismatch_csv_uri"]` is populated so downstream channels can share the link instead of embedding raw payloads.

Helpers

- `src/render/summarize.py` → `summarize_run(result, vars_map)`.
- `src/render/tabular.py` → `markdown_summary_table(result, max_rows, vars_map)`.

Configuration tips

- Increase `max_rows_preview` to include more mismatches in previews.
- Use alerts `send_all_checks` (GChat) to include PASS checks.
- Enable `results_storage.mismatch_csv.enabled` to keep mismatch exports and make the URI available to renderers.
- Use the `table_stats` check (`docs/checks/table_stats.md`) with `stats_storage` to keep `dqf_monitoring.dqf_table_stats` current for downstream monitoring.
- Enable `results_storage.runs` / `results_storage.checks` to persist every run/check row to a table so dashboards can query normalized status data instead of digging through JSON blobs or logs.

