# How To: Run End-to-End

## Goal

Run AGORA's core services and execute end-to-end tests.

## 1) Start infra and migrate

```bash
make up
make migrate-up
```

## 2) Run full tests

```bash
make test-all
make test-e2e
```

If your default `python3` does not have repo deps installed, run with explicit override:

```bash
make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-all
make PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 test-e2e
```

## 3) Manual smoke checks

```bash
curl -sS http://localhost:18000/health
```

Open:
- Core API docs: `http://localhost:18000/docs`
- Temporal UI: `http://localhost:8080`
- Web UI: `http://localhost:3000`
