# Reference: CLI and Commands

AGORA does not provide a single standalone CLI binary today.

Canonical command interface is the repo command map in `Docs/manifest/09_runbook.md`.

Common commands:

- `make up`, `make down`, `make logs`
- `make migrate-up`
- `make dev-core-api`
- `make test`, `make test-all`, `make test-e2e`, `make check-stubs`

Worker entrypoint:

- `python3 apps/worker/main.py`

Moltbook adapter/web use npm scripts inside their app directories.
