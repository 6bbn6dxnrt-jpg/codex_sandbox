"""Synthetic tests only: no live requests or declaration bytes."""
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from local_wealth.pipeline.download import DownloadError, download


class FakeHeaders:
    def __init__(self, content_type="application/pdf", length=None):
        self.content_type = content_type
        self.length = length

    def get_content_type(self):
        return self.content_type

    def get(self, key):
        if key == "Content-Length":
            return self.length
        return None


class FakeResponse:
    def __init__(self, body, content_type="application/pdf", length=None):
        self.body = body
        self.headers = FakeHeaders(content_type, length)
        self.read_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n):
        self.read_calls += 1
        return self.body[:n]


def _request(body, out_dir, content_type="application/pdf", length=None, max_bytes=100):
    response = FakeResponse(body, content_type, length)
    with patch("local_wealth.pipeline.download.urllib.request.urlopen", return_value=response):
        result = download("https://example.org/document", str(out_dir), max_bytes=max_bytes)
    return result, response


@pytest.mark.parametrize("content_type,body,code", [
    ("text/html", b"not a document", "HTML_PAYLOAD"),
    ("application/octet-stream", b"  <html>failed</html>", "HTML_PAYLOAD"),
    ("application/pdf", b"", "EMPTY_BODY"),
    ("application/pdf", b"not-pdf", "BAD_PDF_SIGNATURE"),
    ("application/octet-stream", b"random bytes", "UNSUPPORTED_PAYLOAD"),
    ("image/png", b"not-png", "BAD_IMAGE_SIGNATURE"),
])
def test_bad_payload_is_rejected_without_writing(tmp_path, content_type, body, code):
    raw = tmp_path / "private"
    with pytest.raises(DownloadError, match=code):
        _request(body, raw, content_type)
    assert not raw.exists()


def test_real_pdf_bytes_are_hashed_and_deduplicated(tmp_path):
    body = b"%PDF-1.4\n% synthetic test fixture\n"
    raw = tmp_path / "private"
    first, _ = _request(body, raw, "application/octet-stream")
    second, _ = _request(body, raw)
    expected = hashlib.sha256(body).hexdigest()
    assert first["sha256"] == second["sha256"] == expected
    assert first["bytes"] == len(body)
    assert first["path"] == second["path"]
    assert Path(first["path"]).read_bytes() == body
    assert len(list(raw.iterdir())) == 1


def test_body_limit_enforced_before_persist(tmp_path):
    raw = tmp_path / "private"
    with pytest.raises(DownloadError, match="TOO_LARGE"):
        _request(b"%PDF-1.4 longer than cap", raw, max_bytes=7)
    assert not raw.exists()


def test_content_length_early_rejection_skips_read(tmp_path):
    raw = tmp_path / "private"
    fake = FakeResponse(b"%PDF-1.4 sample", length="999")
    with patch("local_wealth.pipeline.download.urllib.request.urlopen", return_value=fake):
        with pytest.raises(DownloadError, match="TOO_LARGE"):
            download("https://example.org/doc", str(raw), max_bytes=30)
    assert fake.read_calls == 0
    assert not raw.exists()


def test_invalid_content_length_uses_bounded_body(tmp_path):
    raw = tmp_path / "private"
    result, _ = _request(b"%PDF-1.4 short", raw, length="garbage")
    assert result["bytes"] == 14


def test_jpeg_and_png_are_detected_by_signature(tmp_path):
    raw = tmp_path / "private"
    jpeg, _ = _request(b"\xff\xd8\xff\xe0sample", raw, "image/jpeg")
    png, _ = _request(b"\x89PNG\r\n\x1a\nchunk", raw, "image/png")
    assert jpeg["path"].endswith(".jpg")
    assert png["path"].endswith(".png")


def test_relative_or_git_checkout_destination_is_refused():
    with pytest.raises(DownloadError, match="UNSAFE_RAW_DIR"):
        download("https://example.org", "relative/inside/repo")
    repo_dir = Path(__file__).resolve().parents[2]
    with pytest.raises(DownloadError, match="UNSAFE_RAW_DIR"):
        download("https://example.org", str(repo_dir / "private_raw"))


def test_bad_document_does_not_block_next_independent_download(tmp_path):
    raw = tmp_path / "private"
    with pytest.raises(DownloadError, match="HTML_PAYLOAD"):
        _request(b"<html>error</html>", raw, "text/html")
    good, _ = _request(b"%PDF-1.4 valid", raw)
    assert Path(good["path"]).is_file()
