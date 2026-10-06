from local_wealth.pipeline.provenance import (
    bronze_source_ready, silver_source_ready, validate_source_manifest
)

def test_remote_pointer_can_enter_bronze_but_not_silver():
    m = {
        "document_id": "doc-1",
        "source_url": "https://bip.example.pl/file.pdf",
        "retrieval_mode": "remote_pointer",
        "raw_sha256": None,
    }
    assert bronze_source_ready(m)
    assert not silver_source_ready(m)
    assert "RAW_SHA256_REQUIRED" in validate_source_manifest(m, "silver")

def test_raw_bytes_require_hash():
    m = {
        "document_id": "doc-1",
        "source_url": "https://bip.example.pl/file.pdf",
        "retrieval_mode": "raw_bytes",
    }
    assert "RAW_BYTES_WITHOUT_HASH" in validate_source_manifest(m, "bronze")

def test_valid_hashed_source_can_reach_silver():
    m = {
        "document_id": "doc-1",
        "source_url": "https://bip.example.pl/file.pdf",
        "retrieval_mode": "raw_bytes",
        "raw_sha256": "a" * 64,
    }
    assert silver_source_ready(m)
