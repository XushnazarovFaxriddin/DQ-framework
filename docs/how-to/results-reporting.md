# Results & Reporting

Outputs

- Logs: textual summary and markdown table in process output.
- Alerts: Google Chat (text/card) and Email (text + HTML + CSV attachments).

Helpers

- `src/render/summarize.py` → `summarize_run(result, vars_map)`.
- `src/render/tabular.py` → `markdown_summary_table(result, max_rows, vars_map)`.

Configuration tips

- Increase `max_rows_preview` to include more mismatches in previews.
- Use alerts `send_all_checks` (GChat) to include PASS checks.

