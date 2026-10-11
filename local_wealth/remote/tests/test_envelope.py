import json
import tempfile
import unittest
from pathlib import Path
from envelope import generate_keypair, inspect_envelope, open_file, seal_file
from cryptography.exceptions import InvalidTag

class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.private = self.root / 'private.pem'
        self.public = self.root / 'public.pem'
        self.fingerprint = generate_keypair(self.private, self.public)
        self.plain = self.root / 'payload.bin'
        self.plain.write_bytes(b'PRIVATE_SENTINEL_DO_NOT_PUBLISH' * 100000)
        self.sealed = self.root / 'payload.lwe'

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_streaming(self):
        report = seal_file(self.plain, self.sealed, self.public)
        self.assertNotIn(b'PRIVATE_SENTINEL', self.sealed.read_bytes())
        self.assertEqual(report['recipient'], self.fingerprint)
        restored = self.root / 'restored.bin'
        open_file(self.sealed, restored, self.private)
        self.assertEqual(self.plain.read_bytes(), restored.read_bytes())

    def test_tamper_rejected_without_plaintext_output(self):
        seal_file(self.plain, self.sealed, self.public)
        data = bytearray(self.sealed.read_bytes()); data[-32] ^= 1
        self.sealed.write_bytes(data)
        restored = self.root / 'restored.bin'
        with self.assertRaises(InvalidTag):
            open_file(self.sealed, restored, self.private)
        self.assertFalse(restored.exists())
        self.assertFalse(restored.with_suffix('.bin.unauthenticated').exists())

    def test_wrong_key_rejected(self):
        seal_file(self.plain, self.sealed, self.public)
        wrong = self.root / 'wrong.pem'
        generate_keypair(wrong, self.root / 'wrong-public.pem')
        with self.assertRaises(ValueError):
            open_file(self.sealed, self.root / 'restored.bin', wrong)

    def test_existing_key_not_overwritten(self):
        with self.assertRaises(FileExistsError):
            generate_keypair(self.private, self.public)

    def test_plaintext_is_not_envelope(self):
        with self.assertRaises(ValueError):
            inspect_envelope(self.plain)

if __name__ == '__main__':
    unittest.main()
