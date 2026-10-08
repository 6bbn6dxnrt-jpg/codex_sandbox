# Private RAW runner

A standalone bounded worker with local SQLite queue, SHA-256 content-addressed storage, retries and aggregate metrics was built and unit-tested outside the repository. Raw declarations and person-level manifests must be held in private storage, never committed to this public repository.

Production acceptance gate: fetch a real BIP PDF, persist in private RAW, verify SHA-256 after readback, record source provenance, then measure throughput and only then promote to Silver. GitHub Actions alone is not a private durable RAW store. Do not increase downloaded/hash KPIs based on synthetic tests or ephemeral previews.
