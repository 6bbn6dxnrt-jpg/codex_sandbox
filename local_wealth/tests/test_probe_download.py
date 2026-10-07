from local_wealth.benchmark.probe_download import (
    ProbeResult,
    _payload_error,
    summarize,
)


def test_summarize_deduplicates_hashes_and_counts_classes():
    rs = [
        ProbeResult(True, nbytes=100, sha256="a", elapsed_s=1.0, pdf_class="PDF_SCAN"),
        ProbeResult(True, nbytes=200, sha256="a", elapsed_s=1.0, pdf_class="PDF_SCAN"),
        ProbeResult(True, nbytes=300, sha256="b", elapsed_s=1.0, pdf_class="PDF_TEXT"),
        ProbeResult(False, elapsed_s=1.0, error_code="TIMEOUT"),
    ]
    s = summarize(rs)
    assert s["documents_attempted"] == 4
    assert s["documents_downloaded"] == 3
    assert s["unique_hashes"] == 2
    assert s["pdf_classes"] == {"PDF_SCAN": 2, "PDF_TEXT": 1}
    assert s["error_counts"] == {"TIMEOUT": 1}


def test_payload_validation_rejects_html_and_empty_body():
    assert _payload_error("text/html", b"error page") == "HTML_PAYLOAD"
    assert _payload_error("application/octet-stream", b"   <html>error</html>") == "HTML_PAYLOAD"
    assert _payload_error("application/pdf", b"") == "EMPTY_BODY"


def test_payload_validation_requires_pdf_signature_for_pdf_mime():
    assert _payload_error("application/pdf", b"not pdf bytes") == "BAD_PDF_SIGNATURE"
    assert _payload_error("application/pdf", b"%PDF-1.7 sample") is None


def test_payload_validation_accepts_mislabeled_pdf_magic():
    assert _payload_error("application/octet-stream", b"%PDF-1.7 sample") is None
