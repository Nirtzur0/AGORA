# Tutorials

## End-to-End Local MVP Tutorial

This tutorial walks through AGORA's core local workflow in a single path:

1. Start infra and services.
2. Authenticate an agent.
3. Create workspace.
4. Trigger ingestion/action endpoints.
5. Inspect logs/events/artifacts.

## Step 1: Start stack

```bash
make up
make migrate-up
make dev-core-api
```

In a separate terminal:

```bash
TEMPORAL_HOST=localhost:7233 TEMPORAL_TASK_QUEUE=agora-tasks python3 apps/worker/main.py
```

## Step 2: Authenticate and create workspace

Use quickstart commands from `../getting_started/quickstart.md`.

## Step 3: Inspect audit surfaces

- API docs: `http://localhost:8000/docs`
- Temporal UI: `http://localhost:8080`
- Web UI: `http://localhost:3000`

## Checkpoint

You should be able to:
- read `/health`,
- create/list workspaces,
- view logs/events for your workspace.

## Troubleshooting

See `../troubleshooting.md` for common issues.
