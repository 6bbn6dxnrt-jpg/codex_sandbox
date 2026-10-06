from local_wealth.pipeline.qa import validate_field, suspicious_ratio

def test_missing_not_zero_semantics():
    x={"document_id":"d1","extractor_version":"v1","status":"missing","raw_literal":None}
    assert validate_field(x)==[]

def test_read_requires_literal():
    x={"document_id":"d1","extractor_version":"v1","status":"read","raw_literal":None}
    assert "READ_WITHOUT_LITERAL" in validate_field(x)

def test_scale_anomaly():
    assert suspicious_ratio(100000,1000)
