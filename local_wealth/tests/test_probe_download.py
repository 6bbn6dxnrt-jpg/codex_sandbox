from local_wealth.benchmark.probe_download import ProbeResult, summarize

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
