from local_wealth.pipeline.discover import discover_links

def test_direct_attachment_pattern_without_pdf_extension():
    html = '<a href="/attachments/download/20344">Oświadczenie majątkowe - test</a>'
    got = discover_links("https://bip.example.pl/artykul/1", html)
    assert got == [{
        "url": "https://bip.example.pl/attachments/download/20344",
        "label": "Oświadczenie majątkowe - test",
        "kind": "document",
    }]

def test_nested_year_index_is_discovered():
    html = '<a href="/artykul/oswiadczenia-majatkowe-za-2024">Oświadczenia majątkowe za 2024 rok</a>'
    got = discover_links("https://bip.example.pl/artykul/oswiadczenia-majatkowe", html)
    assert got[0]["kind"] == "index"

def test_external_links_are_excluded_by_default():
    html = '<a href="https://other.example/file.pdf">PDF</a>'
    assert discover_links("https://bip.example.pl/x", html) == []

def test_duplicate_urls_are_deduplicated():
    html = '<a href="/x.pdf">A</a><a href="/x.pdf">B</a>'
    got = discover_links("https://bip.example.pl/root", html)
    assert len(got) == 1

def test_underscore_declaration_section_url_is_discovered():
    html = '<a href="/urzad_miejski/oswiadczenia_majatkowe/item.html">record</a>'
    got = discover_links("https://bip.example.pl/urzad_miejski/root.html", html)
    assert got[0]["kind"] == "index"

def test_declaration_section_pagination_url_is_discovered():
    html = '<a href="/oswiadczenia_majatkowe/group.html?pagination%5Boffset%5D=10">2</a>'
    got = discover_links("https://bip.example.pl/oswiadczenia_majatkowe/group.html", html)
    assert got[0]["kind"] == "index"
