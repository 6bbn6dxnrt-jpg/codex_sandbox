"""Bounded download probe for acquisition benchmarking.

The module is safe for the public repository: it stores only code and
aggregate metrics. Declaration bytes must be written to an external/private
RAW directory supplied by the caller and are never committed.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Iterable, Optional
import hashlib
import os
import pathlib
import time
import urllib.error
import urllib.request


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    url: Optional[str] = None
    nbytes: int = 0
    sha256: Optional[str] = None
    elapsed_s: float = 0.0
    content_type: Optional[str] = None
    pdf_class: Optional[str] = None
    error_code: Optional[str] = None


def summarize(results: Iterable[ProbeResult]) -> dict:
    rs = list(results)
    downloaded = [r for r in rs if r.ok]
    hashes = {r.sha256 for r in downloaded if r.sha256}
    classes = Counter(r.pdf_class for r in downloaded if r.pdf_class)
    errors = Counter(r.error_code for r in rs if (not r.ok and r.error_code))
    elapsed = sum(max(0.0, r.elapsed_s) for r in rs)
    return {
        "documents_attempted": len(rs),
        "documents_downloaded": len(downloaded),
        "unique_hashes": len(hashes),
        "bytes_downloaded": sum(max(0, r.nbytes) for r in downloaded),
        "elapsed_s": round(elapsed, 3),
        "documents_per_second": round(len(downloaded) / elapsed, 4) if elapsed else None,
        "pdf_classes": dict(classes),
        "error_counts": dict(errors),
    }


def _classify_pdf(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        return "NON_PDF"
    # Cheap first-pass triage only. A proper PDF parser/OCR stage comes later.
    # Text operators are a useful positive signal but absence is not proof of scan.
    head = data[:2_000_000]
    text_signal = any(tok in head for tok in (b"BT", b"Tj", b"TJ", b"/Font"))
    image_signal = b"/Image" in head or b"/XObject" in head
    if text_signal and not image_signal:
        return "PDF_TEXT"
    if image_signal and not text_signal:
        return "PDF_SCAN"
    return "PDF_MIXED_OR_UNKNOWN"


def probe_url(url: str, raw_dir: str, timeout: int = 30, max_bytes: int = 30_000_000) -> ProbeResult:
    """Download one URL into caller-supplied private RAW storage.

    Idempotency: content is stored by SHA-256, so repeated bytes reuse the same
    target file. The function never chooses a repository-relative destination.
    """
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LocalWealthResearch/0.2"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(max_bytes + 1)
            ctype = r.headers.get_content_type()
        if len(data) > max_bytes:
            return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code="TOO_LARGE")
        sha = hashlib.sha256(data).hexdigest()
        ext = ".pdf" if (ctype == "application/pdf" or data.startswith(b"%PDF-")) else ".bin"
        root = pathlib.Path(raw_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{sha}{ext}"
        if not target.exists():
            target.write_bytes(data)
        return ProbeResult(
            True, url=url, nbytes=len(data), sha256=sha,
            elapsed_s=time.monotonic()-started, content_type=ctype,
            pdf_class=_classify_pdf(data),
        )
    except urllib.error.HTTPError as e:
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code=f"HTTP_{e.code}")
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e)).upper()
        code = "TIMEOUT" if "TIMED OUT" in reason else "NETWORK"
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code=code)
    except TimeoutError:
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code="TIMEOUT")
    except OSError:
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code="IO_ERROR")
