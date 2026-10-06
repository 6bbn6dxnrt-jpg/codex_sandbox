def validate_field(x):
    errors=[]
    if not x.get("document_id"): errors.append("NO_DOCUMENT")
    if not x.get("extractor_version"): errors.append("NO_EXTRACTOR_VERSION")
    if x.get("status")=="read" and x.get("raw_literal") in (None,""): errors.append("READ_WITHOUT_LITERAL")
    c=x.get("confidence")
    if c is not None and not 0 <= c <= 1: errors.append("BAD_CONFIDENCE")
    return errors

def suspicious_ratio(current, previous):
    if current in (None,0) or previous in (None,0): return False
    r=abs(current/previous)
    return r >= 50 or r <= .02
