"""Source-document provenance rules.

Remote pointers are allowed to unblock Bronze benchmarking when byte persistence
is unavailable. They never satisfy Silver/Gold provenance on their own.
"""
from __future__ import annotations

from urllib.parse import urlparse
import re

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

def validate_source_manifest(manifest: dict, target_stage: str = "bronze") -> list[str]:
    errors: list[str] = []
    document_id = manifest.get("document_id")
    source_url = manifest.get("source_url")
    mode = manifest.get("retrieval_mode")
    raw_sha256 = manifest.get("raw_sha256")

    if not document_id:
        errors.append("NO_DOCUMENT_ID")
    if not source_url:
        errors.append("NO_SOURCE_URL")
    else:
        u = urlparse(source_url)
        if u.scheme not in ("http", "https") or not u.netloc:
            errors.append("BAD_SOURCE_URL")
    if mode not in ("raw_bytes", "remote_pointer"):
        errors.append("BAD_RETRIEVAL_MODE")
    if raw_sha256 is not None and not SHA256_RE.fullmatch(str(raw_sha256)):
        errors.append("BAD_RAW_SHA256")

    stage = target_stage.lower()
    if stage in ("silver", "gold", "panel", "analytic") and not raw_sha256:
        errors.append("RAW_SHA256_REQUIRED")
    if mode == "raw_bytes" and not raw_sha256:
        errors.append("RAW_BYTES_WITHOUT_HASH")
    return errors

def bronze_source_ready(manifest: dict) -> bool:
    return not validate_source_manifest(manifest, "bronze")

def silver_source_ready(manifest: dict) -> bool:
    return not validate_source_manifest(manifest, "silver")
