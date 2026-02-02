# Shared Types Package

Shared utilities and types used across AGORA services.

## Contents

### storage.py

Immutable artifact storage on MinIO/S3 with strict URI structure enforcement.

**Features:**
- URI structure validation per spec: `s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/...`
- Immutability enforcement: objects cannot be overwritten
- Clean error handling with specific exceptions
- Support for both bytes and streams

**Usage:**
```python
from storage import Storage, create_storage_from_env

# Create from environment variables
storage = create_storage_from_env()

# Or configure explicitly
storage = Storage(
    endpoint="http://localhost:9000",
    access_key="agora",
    secret_key="agora_dev_password",
    bucket="agora"
)

# Store an object
workspace_id = "..."
artifact_id = "..."
uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v1/document.pdf"
storage.put_object(uri, pdf_bytes)

# Retrieve an object
stream = storage.get_object(uri)
content = stream.read()

# Check existence
if storage.exists(uri):
    print("Object exists")
```

**Exceptions:**
- `ObjectExistsError`: Raised when attempting to overwrite an existing object
- `ObjectNotFoundError`: Raised when requested object doesn't exist
- `InvalidStorageURIError`: Raised when URI doesn't match required structure
- `StorageError`: Base exception for other storage failures

## Installation

```bash
pip install -r requirements.txt
```

## Testing

```bash
# Ensure MinIO is running
make up

# Run storage tests
cd packages/shared-types
pytest test_storage.py -v
```

## Environment Variables

- `S3_ENDPOINT`: MinIO/S3 endpoint URL (default: http://localhost:9000)
- `S3_ACCESS_KEY`: Access key (default: agora)
- `S3_SECRET_KEY`: Secret key (default: agora_dev_password)
- `S3_BUCKET`: Bucket name (default: agora)
