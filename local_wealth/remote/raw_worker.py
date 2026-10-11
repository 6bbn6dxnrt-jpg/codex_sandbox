"""Bounded acquisition of public BIP bytes; all source details stay encrypted.

No full-document OCR, rendering, financial extraction or scientific promotion.
Only aggregate metrics and an encrypted envelope may leave this process.
"""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
import signal
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from envelope import inspect_envelope, public_fingerprint, seal_file

MAX_INDEX_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 400 * 1024 * 1024
USER_AGENT = 'LocalWealthResearch/1.0 (bounded public BIP archive acquisition)'

class FetchDeadlineExceeded(Exception):
    pass

class WallClockDeadline:
    """Linux runner hard deadline, including slow/trickled response bodies."""
    def __init__(self, seconds=60):
        self.seconds = seconds
    def __enter__(self):
        self.previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self.expired)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)
    def expired(self, signum, frame):
        raise FetchDeadlineExceeded('fetch_wall_clock_deadline')
    def __exit__(self, *args):
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self.previous_handler)

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def validate_url(url: str, allowed_host: str, resolve=True):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != allowed_host or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('destination_not_allowed')
    if resolve:
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError('destination_not_public')

class LimitedRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 3
    def __init__(self, allowed_host):
        self.allowed_host = allowed_host
    def redirect_request(self, request, fp, code, message, headers, new_url):
        validate_url(new_url, self.allowed_host)
        return super().redirect_request(request, fp, code, message, headers, new_url)

class PdfLinks(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'a':
            return
        href = dict(attrs).get('href', '')
        absolute = urllib.parse.urljoin(self.base_url, href)
        parts = urllib.parse.urlsplit(absolute)
        if parts.path.lower().endswith('.pdf'):
            clean = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))
            if clean not in self.urls:
                self.urls.append(clean)

class Fetcher:
    def __init__(self, delay=1.0):
        self.last = {}
        self.delay = delay
    def fetch(self, url, allowed_host, max_bytes):
        with WallClockDeadline(60):
            return self._fetch(url, allowed_host, max_bytes)
    def _fetch(self, url, allowed_host, max_bytes):
        validate_url(url, allowed_host)
        opener = urllib.request.build_opener(LimitedRedirect(allowed_host))
        for attempt in range(3):
            elapsed = time.monotonic() - self.last.get(allowed_host, 0)
            time.sleep(max(0, self.delay - elapsed))
            self.last[allowed_host] = time.monotonic()
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity'})
            try:
                with opener.open(request, timeout=25) as response:
                    validate_url(response.geturl(), allowed_host)
                    length = response.headers.get('Content-Length')
                    if length and int(length) > max_bytes:
                        raise ValueError('response_too_large')
                    chunks, size = [], 0
                    while True:
                        chunk = response.read(min(65536, max_bytes + 1 - size))
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError('response_too_large')
                        chunks.append(chunk)
                    return b''.join(chunks), {'http_status': response.status, 'content_type': response.headers.get('Content-Type'), 'final_url': response.geturl(), 'retrieved_at': utcnow()}
            except urllib.error.HTTPError as error:
                if error.code not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                    raise
                retry_after = error.headers.get('Retry-After', '')
                delay = min(15, int(retry_after)) if retry_after.isdigit() else 2 ** (attempt + 1)
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))

def failure_code(error):
    if isinstance(error, urllib.error.HTTPError):
        return 'http_' + str(error.code)
    return type(error).__name__

def validate_pdf_bytes(data):
    if len(data) < 512 or not data.startswith(b'%PDF-') or b'%%EOF' not in data[-4096:]:
        raise ValueError('invalid_pdf_envelope')

def acquire(config_path: Path, public_key: Path, output: Path, max_documents: int = 100):
    if not 1 <= max_documents <= 100:
        raise ValueError('batch_limit_out_of_bounds')
    output.mkdir(parents=True, exist_ok=True)
    if list(output.iterdir()):
        raise ValueError('output_must_be_empty')
    config = json.loads(config_path.read_text())
    if config.get('operation') != 'opaque_public_raw_acquisition':
        raise ValueError('operation_not_allowed')
    sources = config['sources']
    if len(sources) > 6:
        raise ValueError('too_many_indexes')
    started = time.monotonic()
    report = {'schema_version': 1, 'started_at': utcnow(), 'operation': 'opaque_public_raw_acquisition', 'scientific_admitted': False, 'publication_allowed': False, 'documents': [], 'indexes': [], 'failures': [], 'extraction_count': 0}
    metrics = {'index_count': 0, 'discovered_links': 0, 'downloaded_pdfs': 0, 'unique_documents': 0, 'failed_fetches': 0, 'raw_bytes': 0, 'extractions': 0}
    fetcher = Fetcher(delay=1.0)
    visited_urls, seen_hashes = set(), set()
    with tempfile.TemporaryDirectory(prefix='wealth-private-') as temp:
        private_dir = Path(temp)
        raw_dir = private_dir / 'raw'
        raw_dir.mkdir(mode=0o700)
        index_dir = private_dir / 'indexes'
        index_dir.mkdir(mode=0o700)
        for source_index, source in enumerate(sources):
            if metrics['downloaded_pdfs'] >= max_documents or metrics['raw_bytes'] >= MAX_TOTAL_BYTES:
                break
            index_url = source['index_url']
            host = urllib.parse.urlsplit(index_url).hostname
            if host not in config['allowed_hosts']:
                raise ValueError('source_host_not_allowed')
            try:
                content, metadata = fetcher.fetch(index_url, host, MAX_INDEX_BYTES)
                parser = PdfLinks(metadata['final_url'])
                parser.feed(content.decode('utf-8', errors='replace'))
                candidates = []
                for url in parser.urls:
                    try:
                        validate_url(url, host, resolve=False)
                        candidates.append(url)
                    except (ValueError, TypeError):
                        continue
                metrics['index_count'] += 1
                metrics['discovered_links'] += len(candidates)
                index_digest = hashlib.sha256(content).hexdigest()
                index_file = index_dir / (index_digest + '.html')
                index_file.write_bytes(content)
                index_info = {'source_index': source_index, 'index_url': index_url, 'index_sha256': index_digest, 'index_path': 'indexes/' + index_file.name, 'candidate_count': len(candidates), 'candidate_order': candidates, 'metadata': metadata}
                report['indexes'].append(index_info)
            except Exception as error:
                metrics['failed_fetches'] += 1
                report['failures'].append({'stage': 'index', 'source_url': index_url, 'error_class': failure_code(error)})
                continue
            for offset, url in enumerate(candidates):
                if metrics['downloaded_pdfs'] >= max_documents or metrics['raw_bytes'] >= MAX_TOTAL_BYTES or time.monotonic() - started > 900:
                    break
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                try:
                    data, document_metadata = fetcher.fetch(url, host, MAX_PDF_BYTES)
                    validate_pdf_bytes(data)
                    if metrics['raw_bytes'] + len(data) > MAX_TOTAL_BYTES:
                        break
                    digest = hashlib.sha256(data).hexdigest()
                    raw_file = raw_dir / (digest + '.pdf')
                    if digest not in seen_hashes:
                        raw_file.write_bytes(data)
                        if hashlib.sha256(raw_file.read_bytes()).hexdigest() != digest:
                            raise ValueError('raw_readback_mismatch')
                        seen_hashes.add(digest)
                        metrics['unique_documents'] += 1
                        metrics['raw_bytes'] += len(data)
                    metrics['downloaded_pdfs'] += 1
                    report['documents'].append({'document_id': digest, 'sha256': digest, 'source_url': url, 'source_index_url': index_url, 'source_index': source_index, 'index_offset': offset, 'path': 'raw/' + digest + '.pdf', 'bytes': len(data), 'network_acquired': True, 'extraction_allowed': False, 'scientific_admitted': False, 'metadata': document_metadata})
                except Exception as error:
                    metrics['failed_fetches'] += 1
                    report['failures'].append({'stage': 'pdf', 'source_url': url, 'source_index': source_index, 'index_offset': offset, 'error_class': failure_code(error)})
            print(json.dumps({'stage': 'index_complete', **metrics}), flush=True)
        if not metrics['unique_documents']:
            raise RuntimeError('no_documents_acquired')
        report['metrics'] = metrics
        report['finished_at'] = utcnow()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        report['resume_status'] = 'private_merge_required; no automated remote resume claimed'
        (private_dir / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        archive = private_dir / 'checkpoint.zip'
        with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as package:
            package.write(private_dir / 'manifest.json', 'manifest.json')
            for raw_file in sorted(raw_dir.iterdir()):
                package.write(raw_file, 'raw/' + raw_file.name)
            for index_file in sorted(index_dir.iterdir()):
                package.write(index_file, 'indexes/' + index_file.name)
        sealed = output / 'checkpoint.lwe'
        encryption = seal_file(archive, sealed, public_key)
        if encryption['recipient'] != public_fingerprint(public_key.read_bytes()) or encryption['encrypted_bytes'] < 1024:
            sealed.unlink(missing_ok=True)
            raise ValueError('invalid_encrypted_output')
    public_report = {'status': 'encrypted_checkpoint_ready', **metrics, 'elapsed_seconds': round(time.monotonic() - started, 3), **encryption}
    print(json.dumps(public_report), flush=True)
    return public_report

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--public-key', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-documents', type=int, default=100)
    args = parser.parse_args()
    try:
        acquire(args.config, args.public_key, args.output, args.max_documents)
    except Exception as error:
        # Error messages and tracebacks may contain source URLs or page text.
        print(json.dumps({'status': 'failed', 'error_class': type(error).__name__}), file=sys.stderr)
        sys.exit(1)
