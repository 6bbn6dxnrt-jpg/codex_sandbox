import contextlib
import hashlib
import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from envelope import generate_keypair, open_file
from raw_worker import acquire, PdfLinks, validate_url, validate_pdf_bytes, WallClockDeadline, FetchDeadlineExceeded, read_progress

class RawWorkerTests(unittest.TestCase):
    def test_pdf_link_discovery_excludes_nonpdf(self):
        parser = PdfLinks('https://example.gov/index.html')
        parser.feed('<a href="/source.pdf">private name</a><a href="page.html">ignored</a>')
        self.assertEqual(parser.urls, ['https://example.gov/source.pdf'])

    def test_cross_host_and_credentials_disallowed(self):
        for url in ['https://other.gov/a.pdf', 'http://example.gov/a.pdf', 'https://user:password@example.gov/a.pdf', 'https://example.gov:444/a.pdf']:
            with self.assertRaises(ValueError):
                validate_url(url, 'example.gov', resolve=False)

    def test_html_rejected_as_pdf(self):
        with self.assertRaises(ValueError):
            validate_pdf_bytes(b'<html>no pdf</html>' * 100)

    def test_wallclock_deadline_interrupts_slow_response(self):
        started = time.monotonic()
        with self.assertRaises(FetchDeadlineExceeded):
            with WallClockDeadline(0.02):
                time.sleep(0.3)
        self.assertLess(time.monotonic() - started, 0.2)

    def test_personal_fields_rejected_from_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'progress.json'
            path.write_text(json.dumps({'schema_version':1,'indexes':{'0':{'index_sha256':'a'*64,'next_offset':1,'source_url':'PRIVATE'}}}))
            with self.assertRaises(ValueError):
                read_progress(path)

    def test_end_to_end_only_ciphertext_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public, private = root/'public.pem', root/'private.pem'
            generate_keypair(private, public)
            config = root/'config.json'
            config.write_text(json.dumps({'operation':'opaque_public_raw_acquisition','allowed_hosts':['example.gov'],'sources':[{'index_url':'https://example.gov/index.html'}]}))
            index = b'<a href="/PRIVATE_SOURCE.pdf">PRIVATE_NAME</a><a href="/duplicate.pdf">duplicate bytes</a>'
            document = b'%PDF-1.4\n' + b'SYNTHETIC_PRIVATE_DATA_'*80 + b'\n%%EOF\n'
            def fake_fetch(_self, url, host, max_bytes):
                return (index if url.endswith('.html') else document), {'final_url':url,'http_status':200}
            stdout = io.StringIO()
            progress = root/'progress.json'
            with patch('raw_worker.Fetcher.fetch', fake_fetch), contextlib.redirect_stdout(stdout):
                metrics = acquire(config, public, root/'out', progress_cache=progress)
            self.assertEqual(metrics['downloaded_pdfs'], 2)
            self.assertEqual(metrics['unique_documents'], 1)
            self.assertEqual([x.name for x in (root/'out').iterdir()], ['checkpoint.lwe'])
            self.assertNotIn('PRIVATE', stdout.getvalue())
            self.assertNotIn('example.gov', stdout.getvalue())
            self.assertNotIn(b'SYNTHETIC_PRIVATE_DATA', (root/'out/checkpoint.lwe').read_bytes())
            open_file(root/'out/checkpoint.lwe', root/'restored.zip', private)
            with zipfile.ZipFile(root/'restored.zip') as package:
                manifest = json.loads(package.read('manifest.json'))
                self.assertEqual(len(manifest['documents']), 2)
                self.assertEqual(package.read(manifest['documents'][0]['path']), document)
                self.assertFalse(manifest['documents'][0]['extraction_allowed'])
                self.assertEqual(hashlib.sha256(document).hexdigest(), manifest['documents'][0]['sha256'])
                self.assertEqual(package.read(manifest['indexes'][0]['index_path']), index)
            self.assertFalse(progress.exists(), 'Worker must not advance cursor before successful artifact upload')
            pending = progress.with_suffix('.json.pending')
            self.assertTrue(pending.exists())
            pending.replace(progress)  # simulate confirmed artifact upload
            requested = []
            def second_fetch(_self, url, host, max_bytes):
                requested.append(url)
                return fake_fetch(_self, url, host, max_bytes)
            with patch('raw_worker.Fetcher.fetch', second_fetch), contextlib.redirect_stdout(stdout):
                second = acquire(config, public, root/'out2', progress_cache=progress)
            self.assertEqual(second['downloaded_pdfs'], 0)
            self.assertEqual(second['skipped_prior_links'], 2)
            self.assertEqual(requested, ['https://example.gov/index.html'])
            self.assertNotIn('PRIVATE', stdout.getvalue())

if __name__ == '__main__':
    unittest.main()
