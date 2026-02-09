# External Artifacts Store

This directory tracks load-bearing external sources used to justify architecture,
dependency, and reliability decisions.

Structure:
- `index.json`: machine-readable artifact registry (source of truth)
- `blobs/`: optional local snapshots keyed by SHA256
- `excerpts/`: optional short notes/snippets keyed by artifact id

Policy:
- Capture only load-bearing sources (not every URL visited).
- Prefer stable references and official primary docs.
- Include retrieval timestamp for every entry.
- If local blobs are not stored, keep metadata-only entries explicit.
