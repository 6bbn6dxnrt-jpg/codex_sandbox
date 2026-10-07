"""Bounded, validated ingestion of BIP documents into private RAW storage.

This module never writes declaration bytes into a Git checkout. Caller must
pass an absolute path outside the code repository.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import tempfile
import urllib.request


MAX_BYTES = 30_000_000


class DownloadError(ValueError):
    """Machine-readable per-document failure; caller should retry or dead-letter."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _destination(out_dir: str) -> pathlib.Path:
    raw = pathlib.Path(out_dir).expanduser()
    if not raw.is_absolute():
        raise DownloadError("UNSAFE_RAW_DIR")
    root = raw.resolve()
    repo = pathlib.Path(__file__).resolve().parents[2]
    if root == repo or repo in root.parents:
        raise DownloadError("UNSAFE_RAW_DIR")
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise DownloadError("UNSAFE_RAW_DIR")
    return root


def _signature_and_extension(content_type: str, data: bytes) -> str:
    if not data:
        raise DownloadError("EMPTY_BODY")
    prefix = data[:4096].lstrip().lower()
    if (
        content_type in ("text/html", "application/xhtml+xml")
        or prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or b"<html" in prefix[:1024]
    ):
        raise DownloadError("HTML_PAYLOAD")
    if content_type == "application/pdf" and not data.startswith(b"%PDF-"):
        raise DownloadError("BAD_PDF_SIGNATURE")
    if content_type == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
        raise DownloadError("BAD_IMAGE_SIGNATURE")
    if content_type == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise DownloadError("BAD_IMAGE_SIGNATURE")
    if data.startswith(b"%PDF-"):
        return ".pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    raise DownloadError("UNSUPPORTED_PAYLOAD")


def download(url: str, out_dir: str, timeout: int = 30, max_bytes: int = MAX_BYTES) -> dict:
    """Fetch at most max_bytes; validate, SHA-256, and atomically persist privately.

    Only PDF/JPEG/PNG bytes are accepted (including octet-stream mislabeled PDFs).
    Errors are coded so an individual bad source never blocks independent jobs.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be >= 1")
    root = _destination(out_dir)
    req = urllib.request.Request(url, headers={"User-Agent": "LocalWealthResearch/0.4"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get_content_type().lower()
        length = r.headers.get("Content-Length")
        if length:
            try:
                declared_size = int(length)
            except ValueError:
                declared_size = -1
            if declared_size > max_bytes:
                raise DownloadError("TOO_LARGE")
        data = r.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise DownloadError("TOO_LARGE")
    ext = _signature_and_extension(ctype, data)
    sha = hashlib.sha256(data).hexdigest()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / (sha + ext)
    if target.is_symlink():
        raise DownloadError("UNSAFE_RAW_PATH")
    if not target.exists():
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=root, prefix=".raw_", delete=False) as tmp:
                temp_path = pathlib.Path(tmp.name)
                os.chmod(temp_path, 0o600)
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(temp_path, target)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
    return {
        "url": url, "sha256": sha, "content_type": ctype,
        "bytes": len(data), "path": str(target),
    }
