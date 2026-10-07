"""Bounded download probe for acquisition benchmarking.

The module is safe for the public repository: it stores only code and
aggregate metrics. Declaration bytes must be written to an external/private
RAW directory supplied by the caller and are never committed. Ephemeral mode
allows measuring download/hash/triage throughput without persisting bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Iterable, Optional
import hashlib
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
    head = data[:2_000_000]
    text_signal = any(tok in head for tok in (b"BT", b"Tj", b"TJ", b"/Font"))
    image_signal = b"/Image" in head or b"/XObject" in head
    if text_signal and not image_signal:
        return "PDF_TEXT"
    if image_signal and not text_signal:
        return "PDF_SCAN"
    return "PDF_MIXED_OR_UNKNOWN"


def _payload_error(content_type: Optional[str], data: bytes) -> Optional[str]:
    """Return an error code for a successful HTTP response that is not a document.

    BIP endpoints sometimes return an HTML error/login page with HTTP 200. Such
    responses must never inflate download/hash KPIs. PDF MIME responses also
    require the PDF magic signature; mislabeled octet-stream PDFs remain valid
    when the bytes start with the signature.
    """
    if not data:
        return "EMPTY_BODY"

    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    prefix = data[:4096].lstrip().lower()

    if (
        ctype in {"text/html", "application/xhtml+xml"}
        or prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or b"<html" in prefix[:1024]
    ):
        return "HTML_PAYLOAD"

    if ctype == "application/pdf" and not data.startswith(b"%PDF-"):
        return "BAD_PDF_SIGNATURE"

    return None


def _fetch_probe(url: str, timeout: int, max_bytes: int) -> tuple[ProbeResult, Optional[bytes]]:
    """Fetch once and return a result plus bytes for optional private persistence."""
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LocalWealthResearch/0.4"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(max_bytes + 1)
            ctype = r.headers.get_content_type()
        if len(data) > max_bytes:
            return ProbeResult(
                False, url=url, elapsed_s=time.monotonic() - started,
                error_code="TOO_LARGE"
            ), None

        payload_error = _payload_error(ctype, data)
        if payload_error:
            return ProbeResult(
                False,
                url=url,
                nbytes=len(data),
                elapsed_s=time.monotonic() - started,
                content_type=ctype,
                error_code=payload_error,
            ), None

        sha = hashlib.sha256(data).hexdigest()
        return ProbeResult(
            True, url=url, nbytes=len(data), sha256=sha,
            elapsed_s=time.monotonic() - started, content_type=ctype,
            pdf_class=_classify_pdf(data),
        ), data
    except urllib.error.HTTPError as e:
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code=f"HTTP_{e.code}"), None
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e)).upper()
        code = "TIMEOUT" if "TIMED OUT" in reason else "NETWORK"
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code=code), None
    except TimeoutError:
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code="TIMEOUT"), None
    except OSError:
        return ProbeResult(False, url=url, elapsed_s=time.monotonic()-started, error_code="IO_ERROR"), None


def probe_url_ephemeral(url: str, timeout: int = 30, max_bytes: int = 30_000_000) -> ProbeResult:
    """Fetch/hash/triage one URL without retaining declaration bytes.

    This mode is for throughput benchmarking when private RAW persistence is
    unavailable. It does not satisfy Silver provenance because bytes are not
    retained durably.
    """
    result, _ = _fetch_probe(url, timeout=timeout, max_bytes=max_bytes)
    return result


def probe_urls_ephemeral(
    urls: Iterable[str],
    timeout: int = 30,
    max_bytes: int = 30_000_000,
    max_documents: int = 100,
) -> list[ProbeResult]:
    """Run a bounded sequential benchmark without retaining declaration bytes.

    Each URL is isolated: a failed fetch is encoded in its ProbeResult and does
    not block later URLs. max_documents prevents accidental unbounded network
    work in benchmark jobs.
    """
    if max_documents < 1:
        raise ValueError("max_documents must be >= 1")

    results: list[ProbeResult] = []
    for url in urls:
        if len(results) >= max_documents:
            break
        results.append(
            probe_url_ephemeral(url, timeout=timeout, max_bytes=max_bytes)
        )
    return results


def probe_url(url: str, raw_dir: str, timeout: int = 30, max_bytes: int = 30_000_000) -> ProbeResult:
    """Download one URL into caller-supplied private RAW storage.

    Idempotency: content is stored by SHA-256, so repeated bytes reuse the same
    target file. The function never chooses a repository-relative destination.
    """
    result, data = _fetch_probe(url, timeout=timeout, max_bytes=max_bytes)
    if not result.ok or data is None:
        return result
    try:
        ext = ".pdf" if (result.content_type == "application/pdf" or data.startswith(b"%PDF-")) else ".bin"
        root = pathlib.Path(raw_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{result.sha256}{ext}"
        if not target.exists():
            target.write_bytes(data)
        return result
    except OSError:
        return ProbeResult(
            False, url=url, elapsed_s=result.elapsed_s,
            error_code="IO_ERROR"
        )
