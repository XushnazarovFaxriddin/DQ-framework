# Results Model

Dataclasses (`src/runtime/results.py`)

```
CheckResult:
  table: str
  check_type: str
  status: PASS | FAIL | SKIP
  details: dict

RunResult:
  overall_status: PASS|FAIL (derived)
  checks: [CheckResult]
```

Rendering helpers

- Text summary: `src/render/summarize.py` → `summarize_run`.
- Markdown table: `src/render/tabular.py` → `markdown_summary_table`.
  - Aggregations expand each rule as its own row.
  - Details truncated by `max_details_chars` (default 1200; configurable via vars).

Email previews

- For detail keys like `missing_on_target`, `extra_on_target`, `mismatch_sample`, `diff_sample`, CSV attachments are added (limited by `max_rows_preview`).

