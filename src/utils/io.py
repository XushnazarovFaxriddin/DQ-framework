"""
Artifacts IO utilities:
- Save CSV/Parquet previews into a local artifacts directory.
- Store mismatch CSVs in pluggable storage backends.
- Export mismatch IDs with templated paths for dashboard integration.

Env:
  DQF_ARTIFACTS_DIR: base directory for artifacts (default: ./artifacts)
"""

import csv
import io as io_module
import os
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping as MappingABC
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, TYPE_CHECKING

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.compiler.schema import MismatchCsvCfg, MismatchIdsCfg
from src.utils.logger import log

if TYPE_CHECKING:
    from src.utils.mismatch_ids import MismatchIdsResult


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


def _get_est_datetime() -> datetime:
    """Get current datetime in EST timezone."""
    try:
        from zoneinfo import ZoneInfo
        est = ZoneInfo("America/New_York")
    except ImportError:
        # Fallback for Python < 3.9
        from datetime import timedelta
        est_offset = timedelta(hours=-5)

        class EST(timezone):
            def __init__(self):
                super().__init__(est_offset, "EST")

        est = EST()

    return datetime.now(est)


def _build_templated_path(
    template: str,
    *,
    config_file: str = "",
    check_name: str = "",
    table_name: str = "",
) -> str:
    """
    Build file path from template with variable substitution.

    Supported variables:
    - {config_file}: Name of the config file (without extension)
    - {check_name}: Type of check (e.g., "row_count", "aggregations")
    - {table_name}: Name of the table being validated
    - {date}: Date in YYYYMMDD_HHMMSS format (EST timezone)
    - {timestamp}: Unix timestamp
    - {uuid}: Short UUID for uniqueness

    Example: "{config_file}/{check_name}/{table_name}-{date}.csv"
    """
    est_now = _get_est_datetime()
    date_str = est_now.strftime("%Y%m%d_%H%M%S")
    timestamp = int(time.time())
    uid = uuid.uuid4().hex[:8]

    # Clean inputs
    config_file_clean = _slugify(config_file) if config_file else "default"
    check_name_clean = _slugify(check_name) if check_name else "check"
    table_name_clean = _slugify(table_name) if table_name else "table"

    path = template.format(
        config_file=config_file_clean,
        check_name=check_name_clean,
        table_name=table_name_clean,
        date=date_str,
        timestamp=timestamp,
        uuid=uid,
    )

    return path


def _build_mismatch_ids_storage_backend(cfg: MismatchIdsCfg) -> StorageBackend:
    """Build storage backend for mismatch IDs export."""
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
                "mismatch_ids.backend.fallback",
                level="WARNING",
                backend="gcs",
                error=str(exc),
                action="using_local_storage",
            )
            return LocalStorageBackend(base_path=base_path, public_url_prefix=None)
    return LocalStorageBackend(base_path=base_path, public_url_prefix=cfg.public_url_prefix)


def persist_mismatch_ids_csv(
    *,
    mismatch_result: "MismatchIdsResult",
    cfg: Optional[MismatchIdsCfg],
    config_file: str = "",
    check_name: str = "",
    table_name: str = "",
) -> Optional[Dict[str, str]]:
    """
    Persist mismatch IDs to CSV with templated path.

    Returns dict with:
    - combined_uri: URI to combined CSV (all mismatches)
    - missing_in_target_uri: URI to missing IDs CSV (if separate_files=True)
    - extra_in_target_uri: URI to extra IDs CSV (if separate_files=True)
    """
    if not cfg or not cfg.enabled:
        return None

    if not mismatch_result:
        return None

    rows = mismatch_result.to_csv_rows()
    if not rows:
        return None

    backend = _build_mismatch_ids_storage_backend(cfg)
    result_uris: Dict[str, str] = {}

    # Build path from template
    file_path = _build_templated_path(
        cfg.path_template,
        config_file=config_file,
        check_name=check_name,
        table_name=table_name,
    )

    # Export combined CSV
    csv_bytes = _rows_to_csv_bytes(rows)
    if csv_bytes:
        uri = backend.upload(file_path, csv_bytes)
        result_uris["combined_uri"] = uri
        log(
            "mismatch_ids.csv.exported",
            table=table_name,
            check=check_name,
            uri=uri,
            total_rows=len(rows),
            missing_in_target=mismatch_result.missing_in_target_count,
            extra_in_target=mismatch_result.extra_in_target_count,
        )

    # Export separate files if configured
    if cfg.separate_files:
        # Missing in target
        missing_rows = [r for r in rows if r.get("mismatch_type") == "missing_in_target"]
        if missing_rows:
            missing_path = file_path.replace(".csv", "-missing_in_target.csv")
            missing_bytes = _rows_to_csv_bytes(missing_rows)
            if missing_bytes:
                result_uris["missing_in_target_uri"] = backend.upload(missing_path, missing_bytes)

        # Extra in target (CRITICAL)
        extra_rows = [r for r in rows if r.get("mismatch_type") == "extra_in_target"]
        if extra_rows:
            extra_path = file_path.replace(".csv", "-extra_in_target.csv")
            extra_bytes = _rows_to_csv_bytes(extra_rows)
            if extra_bytes:
                result_uris["extra_in_target_uri"] = backend.upload(extra_path, extra_bytes)
                log(
                    "mismatch_ids.critical.exported",
                    level="WARNING",
                    table=table_name,
                    check=check_name,
                    uri=result_uris["extra_in_target_uri"],
                    extra_in_target_count=len(extra_rows),
                    message="CRITICAL: Exported IDs that exist in target but not in source",
                )

    return result_uris if result_uris else None


def attach_mismatch_ids_uris(details: Dict[str, Any], uris: Dict[str, str]) -> None:
    """Attach mismatch IDs URIs to check result details."""
    if not uris:
        return

    details["mismatch_ids_uris"] = uris

    if "combined_uri" in uris:
        # Also add to standard mismatch_csv_uris for compatibility
        attach_csv_uri(details, uris["combined_uri"])

    if "extra_in_target_uri" in uris:
        details["extra_in_target_csv_uri"] = uris["extra_in_target_uri"]
        details["has_extra_in_target"] = True
