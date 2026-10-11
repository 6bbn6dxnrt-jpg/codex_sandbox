# Encrypted remote acquisition

This worker fetches opaque PDF bytes from registered official pilot indexes. It does not render full pages, OCR documents, extract financial fields, or admit observations scientifically. All PDFs, individual source URLs, index contents and row-level manifests stay inside a temporary private directory and an authenticated encrypted envelope. Public logs contain aggregate metrics only.

`recipient-public.pem` is safe to commit. The corresponding private key must be saved privately and its readback verified before running this workflow. Never commit the private key. Encryption is RSA-3072 OAEP-SHA256 wrapping a fresh AES-256-GCM key; the complete envelope header is authenticated. Decryption does not make an output available until authentication succeeds.

The workflow belongs at root `.github/workflows/local-wealth-encrypted-smoke.yml`; other files belong in `local_wealth/remote/`. Actions are pinned to their official tag commit SHAs. It uploads only `checkpoint.lwe`, never an unencrypted ZIP or manifest, and only after successful acquisition and encryption checks. An ephemeral runner and an expiring encrypted artifact are not themselves permanent corpus storage. Download, decrypt, verify and persist each checkpoint privately.

The first run is push-triggered and capped at 100 documents, 400 MiB total, three registered pilot indexes, one request per host per second, a hard 60-second wall-clock deadline per fetch including retries and response body, and a 25-minute job timeout. The registered pilot may contain fewer than 100 documents. Failures are isolated; no PDF means the run fails without uploading an artifact. No schedule is enabled yet. Remote resume remains unproven until a decrypted checkpoint has been merged privately and a subsequent run has demonstrated no duplicate corpus entries.

Local tests: `PYTHONPATH=remote python -m unittest discover -s remote/tests -v` from the package root. Use `python remote/envelope.py decrypt --private <private-key> --source <checkpoint.lwe> --target <new-checkpoint.zip>` in a private workspace. A wrong key or altered envelope fails closed.
