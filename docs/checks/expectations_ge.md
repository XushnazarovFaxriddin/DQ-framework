# Great Expectations (Adapter)

Purpose: run GE expectations either inline on a Pandas dataset or via a GE Checkpoint.

Modes (`src/checks/expectations/ge_adapter.py`):

1) Pandas mode (inline expectations or `suite_file`)
   - Fetch a DataFrame using connector `fetch_df(sql)` (rendered from table cfg or provided `query`)
   - Execute expectations against it
2) Checkpoint mode (advanced)
   - Execute an existing GE checkpoint from a GE context directory

Config (first `rules` item is used)

```
type: ge_expectations
rules:
  - 'on': source | target              # default: source  (YAML: quote the key 'on')
    query: <SQL>                       # optional; otherwise rendered from table_cfg
    limit: 5000                        # optional limit for Pandas mode
    suite_file: path/to/suite.yaml     # optional
    expectations: [ {expectation_type, kwargs}, ... ]
    # OR checkpoint mode:
    checkpoint_file: path/to/checkpoint.yml
    gx_context_dir: path/to/great_expectations
    variables: { key: value }
```

Examples

```
# Inline expectations
- type: ge_expectations
  rules:
    - 'on': source
      expectations:
        - expectation_type: expect_column_values_to_not_be_null
          kwargs: { column: id }
        - expectation_type: expect_table_row_count_to_be_between
          kwargs: { min_value: 1 }

# Suite file
- type: ge_expectations
  rules:
    - suite_file: ge/suites/users.yaml

# Checkpoint
- type: ge_expectations
  rules:
    - checkpoint_file: ge/checkpoints/orders.yml
      gx_context_dir: ge
      variables: { run_label: "{{ run_label }}" }
```

Details output

- Summary of failures/stats, truncated for compact reporting.

Notes

- Requires `great_expectations` installed.
- In Pandas mode, uses either `great_expectations.dataset.PandasDataset` or `ge.from_pandas` (fallback).
- Always quote `'on'` in YAML. See Reference → YAML Quoting Rules.

