# Results Model

Dataclasses (`src/runtime/results.py`)

```py
CheckResult:
  table: str
  check_type: str
  status: PASS | FAIL | SKIP
  details: dict
  severity: INFO | WARNING | CRITICAL (optional; defaults to WARNING for FAILs)

RunResult:
  overall_status: PASS|FAIL (derived)
  overall_severity: INFO | WARNING | CRITICAL (derived from failing checks)
  checks: [CheckResult]
```

Rendering helpers

- Text summary: `src/render/summarize.py` → `summarize_run`.
- Markdown table: `src/render/tabular.py` → `markdown_summary_table`.
  - Aggregations expand each rule as its own row.
  - Details truncated by `max_details_chars` (default 1200; configurable via vars).

Email previews

- For detail keys like `missing_on_target`, `extra_on_target`, `mismatch_sample`, `diff_sample`, CSV attachments are added (limited by `max_rows_preview`).

Mismatch CSV links

- When `results_storage.mismatch_csv` is enabled and mismatch ranges are exported, `CheckResult.details` may include `mismatch_csv_uri` (first link) and `mismatch_csv_uris` (all links). Alert renderers can use `src/render/mismatch_links.py` to discover the URIs and surface them to users.

Severity

- Failing checks can now declare `severity` (INFO/WARNING/CRITICAL); if omitted, FAILs default to WARNING. The run-level `overall_severity` is derived from the worst failing check and is surfaced in alert headers/subjects for easier triage.
- When `results_storage.runs/checks` is configured, each run and check emits a normalized row (status, severity, counts, references) into the target table so analytics pipelines can read DQF outcomes without parsing nested JSON.

