"""
Artifacts IO utilities:
- Save CSV/Parquet previews into a local artifacts directory.
- (Optional) In the future, extend to upload to S3/GCS and return signed URLs.

Env:
  DQF_ARTIFACTS_DIR: base directory for artifacts (default: ./artifacts)
"""

import os
from typing import Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def _artifacts_dir() -> str:
    return os.getenv("DQF_ARTIFACTS_DIR", os.path.abspath("./artifacts"))


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_preview_csv(df: pd.DataFrame, name: str) -> str:
    base = _artifacts_dir()
    ensure_dir(base)
    path = os.path.join(base, f"{name}.csv")
    df.to_csv(path, index=False)
    return path


def save_preview_parquet(df: pd.DataFrame, name: str) -> str:
    base = _artifacts_dir()
    ensure_dir(base)
    path = os.path.join(base, f"{name}.parquet")
    table = pa.Table.from_pandas(df)
    pq.write_table(table, path)
    return path
