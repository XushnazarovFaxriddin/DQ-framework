"""
Artifacts IO utilities:
- Save CSV/Parquet previews into a local artifacts directory.
- Store mismatch CSVs in pluggable storage backends.

Env:
  DQF_ARTIFACTS_DIR: base directory for artifacts (default: ./artifacts)
"""

import csv
import io as io_module
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping as MappingABC
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.compiler.schema import MismatchCsvCfg
from src.utils.logger import log


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


class StorageBackend(ABC):
    def __init__(self, base_path: str, public_url_prefix: Optional[str]) -> None:
        self._base_path = base_path.strip("/ ") if base_path else ""
        self._public_url_prefix = public_url_prefix

    def _prefixed_path(self, name: str) -> str:
        if self._base_path:
            return f"{self._base_path.rstrip('/')}/{name}"
        return name

    def _public_uri(self, object_path: str) -> str:
        if self._public_url_prefix:
            prefix = self._public_url_prefix.rstrip("/")
            return f"{prefix}/{object_path}"
        return object_path

    @abstractmethod
    def upload(self, name: str, data: bytes) -> str:
        ...


class LocalStorageBackend(StorageBackend):
    def upload(self, name: str, data: bytes) -> str:
        object_path = self._prefixed_path(name)
        path = os.path.join(_artifacts_dir(), object_path)
        ensure_dir(os.path.dirname(path))
        with open(path, "wb") as handle:
            handle.write(data)
        if self._public_url_prefix:
            return self._public_uri(object_path)
        return os.path.abspath(path)


class GCSStorageBackend(StorageBackend):
    def __init__(
        self,
        bucket: str,
        base_path: str,
        public_url_prefix: Optional[str],
    ) -> None:
        super().__init__(base_path, public_url_prefix)
        try:
            from google.cloud import storage
        except ImportError as exc:
            raise RuntimeError(
                "GCS storage backend requires 'google-cloud-storage' package"
            ) from exc
        self._bucket_name = bucket
        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket)

    def upload(self, name: str, data: bytes) -> str:
        object_path = self._prefixed_path(name)
        blob = self._bucket.blob(object_path)
        blob.upload_from_string(data, content_type="text/csv")
        if self._public_url_prefix:
            return self._public_uri(object_path)
        return f"gs://{self._bucket_name}/{object_path}"


def _normalize_row(row: Any) -> Dict[str, Any]:
    if isinstance(row, MappingABC):
        return dict(row)
    if isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
        return {f"column_{idx}": value for idx, value in enumerate(row)}
    return {"value": row}


def _build_headers(normalized_rows: Sequence[Dict[str, Any]]) -> Sequence[str]:
    seen: set[str] = set()
    headers: list[str] = []
    for row in normalized_rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                headers.append(key)
    return headers


def _rows_to_csv_bytes(normalized_rows: Sequence[Dict[str, Any]]) -> bytes:
    headers = _build_headers(normalized_rows)
    if not headers:
        return b""
    buffer = io_module.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in normalized_rows:
        writer.writerow({key: row.get(key) for key in headers})
    return buffer.getvalue().encode("utf-8")


def _build_storage_backend(cfg: MismatchCsvCfg) -> StorageBackend:
    base_path = cfg.base_path or ""
    if cfg.backend == "gcs":
        if not cfg.bucket:
            raise ValueError("GCS backend configured but 'bucket' is missing")
        try:
            return GCSStorageBackend(
                bucket=cfg.bucket,
                base_path=base_path,
                public_url_prefix=cfg.public_url_prefix,
            )
        except Exception as exc:
            log(
                "mismatch_csv.backend.fallback",
                level="WARNING",
                backend="gcs",
                error=str(exc),
                action="using_local_storage",
            )
            return LocalStorageBackend(base_path=base_path, public_url_prefix=None)
    return LocalStorageBackend(base_path=base_path, public_url_prefix=cfg.public_url_prefix)


def _slugify(text: str) -> str:
    allowed = "-"
    safe: list[str] = []
    for char in text.lower():
        if char.isalnum() or char in allowed:
            safe.append(char)
        else:
            safe.append("-")
    slug = "".join(safe).strip("-")
    return slug or "value"


def _build_file_name(label: str, vars_map: Mapping[str, Any]) -> str:
    run_label = vars_map.get("run_label") or vars_map.get("env") or "run"
    prefix = _slugify(str(run_label))
    label_slug = _slugify(label)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    uid = uuid.uuid4().hex[:8]
    return f"{prefix}-{label_slug}-{timestamp}-{uid}.csv"


def persist_rows_csv(
    *,
    rows: Sequence[Mapping[str, Any]],
    label: str,
    vars_map: Mapping[str, Any],
    cfg: Optional[MismatchCsvCfg],
) -> Optional[str]:
    if not cfg or not cfg.enabled:
        return None
    normalized_rows = [_normalize_row(row) for row in rows]
    if not normalized_rows:
        return None
    backend = _build_storage_backend(cfg)
    content = _rows_to_csv_bytes(normalized_rows)
    if not content:
        return None
    file_name = _build_file_name(label, vars_map)
    return backend.upload(file_name, content)


def attach_csv_uri(details: Dict[str, Any], uri: str) -> None:
    if not uri:
        return
    uris = details.setdefault("mismatch_csv_uris", [])
    if uri not in uris:
        uris.append(uri)
    details.setdefault("mismatch_csv_uri", uris[0])
