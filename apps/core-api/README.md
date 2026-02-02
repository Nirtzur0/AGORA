# Core API

FastAPI application implementing the AGORA platform's REST API, authentication, authorization, and orchestration.

## Structure

```
core-api/
├── main.py           # FastAPI app with health endpoint
├── config.py         # Environment-based configuration
├── requirements.txt  # Production dependencies
└── requirements-dev.txt  # Development/test dependencies
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run the server
python main.py

# Or with auto-reload
uvicorn main:app --reload --port 8000
```

## Testing

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

## Environment Variables

See `infra/README.md` for full environment variable documentation.

Required variables:
- `DATABASE_URL`: Postgres connection string
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`: MinIO/S3 config
- `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `TEMPORAL_TASK_QUEUE`: Temporal config
- `MOLTBOOK_ADAPTER_URL`: Moltbook adapter service URL
- `JWT_SECRET_KEY`, `SERVICE_JWT_SECRET_KEY`: JWT signing keys
