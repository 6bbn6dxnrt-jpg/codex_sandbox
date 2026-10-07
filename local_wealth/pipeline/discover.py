"""Bounded HTML discovery for BIP declaration pages.

Emits only link metadata; no declaration contents or personal data are stored.
"""
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
import re

DECLARATION_TERMS = (
    "oświadczenie majątkowe",
    "oświadczenia majątkowe",
    "oswiadczenie majatkowe",
    "oswiadczenia majatkowe",
)
DOCUMENT_EXT_RE = re.compile(r"\.(pdf|jpg|jpeg|png)(?:$|[?#])", re.I)
SEPARATOR_RE = re.compile(r"[-_]+")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


def same_host(a, b):
    return (urlparse(a).hostname or "").lower() == (urlparse(b).hostname or "").lower()


def _normalized_haystack(label: str, url: str) -> str:
    """Normalize common BIP URL separators before declaration-term matching.

    Some BIP installations encode the declaration section as
    oswiadczenia_majatkowe or oswiadczenia-majatkowe while person-page
    labels contain only a person's name. Treating separators as spaces keeps
    those pages and their pagination links discoverable without relying on names.
    """
    text = unquote(f"{label} {url}").lower()
    return SEPARATOR_RE.sub(" ", text)


def discover_links(page_url, html, same_host_only=True):
    parser = LinkParser()
    parser.feed(html)
    seen, out = set(), []
    for href, label in parser.links:
        if not href:
            continue
        url = urljoin(page_url, href)
        if same_host_only and not same_host(page_url, url):
            continue
        hay = _normalized_haystack(label, url)
        kind = None
        if DOCUMENT_EXT_RE.search(url) or "/attachments/download/" in url.lower():
            kind = "document"
        elif any(term in hay for term in DECLARATION_TERMS):
            kind = "index"
        if kind and url not in seen:
            seen.add(url)
            out.append({"url": url, "label": label, "kind": kind})
    return out
