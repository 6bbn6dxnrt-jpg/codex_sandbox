def classify(content_type, data):
    if content_type=="application/pdf" or data[:5]==b"%PDF-": return "PDF_UNTRIAGED"
    if content_type in ("image/jpeg","image/png"): return "IMAGE"
    if content_type in ("text/html","application/xhtml+xml"): return "HTML"
    return "UNKNOWN"
