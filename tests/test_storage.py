"""
Integration tests for storage module.

Tests verify:
- Store and retrieve bytes roundtrip
- Immutability enforcement (no overwrites)
- Storage URI structure validation
- Error handling
"""
import pytest
import os
import uuid
from io import BytesIO

from storage import (
    Storage,
    StorageError,
    ObjectExistsError,
    ObjectNotFoundError,
    InvalidStorageURIError,
    create_storage_from_env
)


@pytest.fixture(scope="module")
def storage():
    """Create storage instance for tests."""
    # Use test bucket
    return Storage(
        endpoint=os.getenv('S3_ENDPOINT', 'http://localhost:9000'),
        access_key=os.getenv('S3_ACCESS_KEY', 'agora'),
        secret_key=os.getenv('S3_SECRET_KEY', 'agora_dev_password'),
        bucket='agora-test',
    )


@pytest.fixture
def test_workspace_id():
    """Generate unique workspace ID for tests."""
    return str(uuid.uuid4())


@pytest.fixture
def test_artifact_id():
    """Generate unique artifact ID for tests."""
    return str(uuid.uuid4())


def make_storage_uri(workspace_id: str, artifact_id: str, version: int, filename: str = "content") -> str:
    """Helper to construct valid storage URI."""
    return f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/{filename}"


class TestStorageURIValidation:
    """Test storage URI structure validation."""
    
    def test_valid_uri_passes(self, storage, test_workspace_id, test_artifact_id):
        """Valid URI structure should pass validation."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 1, "test.pdf")
        # Should not raise
        key = storage._validate_storage_uri(uri)
        assert key.startswith(test_workspace_id)
        assert "artifacts" in key
        assert test_artifact_id in key
        assert "v1" in key
    
    def test_invalid_scheme_fails(self, storage):
        """Invalid scheme should raise error."""
        with pytest.raises(InvalidStorageURIError, match="Invalid scheme"):
            storage._validate_storage_uri("http://agora/workspace/artifacts/a1/v1/file")
    
    def test_invalid_bucket_fails(self, storage):
        """Invalid bucket name should raise error."""
        with pytest.raises(InvalidStorageURIError, match="Invalid bucket"):
            storage._validate_storage_uri("s3://wrong-bucket/workspace/artifacts/a1/v1/file")
    
    def test_missing_artifacts_component_fails(self, storage, test_workspace_id):
        """Missing 'artifacts' component should raise error."""
        with pytest.raises(InvalidStorageURIError, match="must be 'artifacts'"):
            storage._validate_storage_uri(f"s3://agora/{test_workspace_id}/wrong/a1/v1/file")
    
    def test_invalid_version_format_fails(self, storage, test_workspace_id, test_artifact_id):
        """Version must start with 'v'."""
        with pytest.raises(InvalidStorageURIError, match="must start with 'v'"):
            storage._validate_storage_uri(
                f"s3://agora/{test_workspace_id}/artifacts/{test_artifact_id}/1/file"
            )
    
    def test_too_short_path_fails(self, storage):
        """Path must have minimum required components."""
        with pytest.raises(InvalidStorageURIError, match="Invalid path structure"):
            storage._validate_storage_uri("s3://agora/workspace/artifacts")


class TestBasicOperations:
    """Test basic put/get/exists operations."""
    
    def test_put_and_get_bytes_roundtrip(self, storage, test_workspace_id, test_artifact_id):
        """Store bytes and retrieve them exactly."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 1, "test.txt")
        content = b"Hello, AGORA! This is test content."
        
        # Store
        storage.put_object(uri, content)
        
        # Verify exists
        assert storage.exists(uri)
        
        # Retrieve
        stream = storage.get_object(uri)
        retrieved = stream.read()
        
        # Verify exact match
        assert retrieved == content
    
    def test_put_and_get_stream_roundtrip(self, storage, test_workspace_id, test_artifact_id):
        """Store stream and retrieve it exactly."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 2, "stream.bin")
        content = b"Binary content with \x00 null bytes \xFF and unicode: \xc3\xa9"
        stream = BytesIO(content)
        
        # Store
        storage.put_object(uri, stream)
        
        # Retrieve
        retrieved_stream = storage.get_object(uri)
        retrieved = retrieved_stream.read()
        
        # Verify exact match
        assert retrieved == content
    
    def test_exists_returns_false_for_nonexistent(self, storage, test_workspace_id, test_artifact_id):
        """Exists should return False for objects that don't exist."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 999, "nonexistent.txt")
        assert not storage.exists(uri)
    
    def test_get_nonexistent_raises_error(self, storage, test_workspace_id, test_artifact_id):
        """Getting non-existent object should raise ObjectNotFoundError."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 999, "missing.txt")
        
        with pytest.raises(ObjectNotFoundError, match="Object not found"):
            storage.get_object(uri)


class TestImmutability:
    """Test immutability enforcement (no overwrites)."""
    
    def test_overwrite_same_uri_fails(self, storage, test_workspace_id, test_artifact_id):
        """Attempting to overwrite existing object should raise ObjectExistsError."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 3, "immutable.txt")
        
        # First write succeeds
        content1 = b"Original content"
        storage.put_object(uri, content1)
        
        # Second write to same URI must fail
        content2 = b"Attempted overwrite"
        with pytest.raises(ObjectExistsError, match="already exists"):
            storage.put_object(uri, content2)
        
        # Verify original content is preserved
        retrieved = storage.get_object(uri).read()
        assert retrieved == content1
    
    def test_different_versions_can_coexist(self, storage, test_workspace_id, test_artifact_id):
        """Different versions of same artifact can be stored."""
        base_path = f"s3://agora/{test_workspace_id}/artifacts/{test_artifact_id}"
        
        # Store v1
        uri_v1 = f"{base_path}/v1/content"
        content_v1 = b"Version 1 content"
        storage.put_object(uri_v1, content_v1)
        
        # Store v2 (different version, different URI)
        uri_v2 = f"{base_path}/v2/content"
        content_v2 = b"Version 2 content"
        storage.put_object(uri_v2, content_v2)
        
        # Both should exist and be retrievable
        assert storage.exists(uri_v1)
        assert storage.exists(uri_v2)
        
        retrieved_v1 = storage.get_object(uri_v1).read()
        retrieved_v2 = storage.get_object(uri_v2).read()
        
        assert retrieved_v1 == content_v1
        assert retrieved_v2 == content_v2
    
    def test_multiple_artifacts_in_workspace_independent(self, storage, test_workspace_id):
        """Multiple artifacts in same workspace are independent."""
        artifact1 = str(uuid.uuid4())
        artifact2 = str(uuid.uuid4())
        
        uri1 = make_storage_uri(test_workspace_id, artifact1, 1, "file1.txt")
        uri2 = make_storage_uri(test_workspace_id, artifact2, 1, "file2.txt")
        
        content1 = b"Artifact 1 content"
        content2 = b"Artifact 2 content"
        
        storage.put_object(uri1, content1)
        storage.put_object(uri2, content2)
        
        # Both should exist independently
        assert storage.get_object(uri1).read() == content1
        assert storage.get_object(uri2).read() == content2


class TestLargeContent:
    """Test handling of larger content."""
    
    def test_large_binary_content(self, storage, test_workspace_id, test_artifact_id):
        """Handle larger binary files (simulating PDFs, images)."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 4, "large.bin")
        
        # Create 1MB of content
        content = os.urandom(1024 * 1024)
        
        storage.put_object(uri, content)
        retrieved = storage.get_object(uri).read()
        
        assert len(retrieved) == len(content)
        assert retrieved == content


class TestEnvironmentFactory:
    """Test factory function for creating storage from environment."""
    
    def test_create_from_env(self):
        """Should create storage from environment variables."""
        storage = create_storage_from_env()
        assert storage is not None
        assert storage.bucket == os.getenv('S3_BUCKET', 'agora')


class TestErrorHandling:
    """Test error handling edge cases."""
    
    def test_empty_content_allowed(self, storage, test_workspace_id, test_artifact_id):
        """Empty content should be allowed (e.g., empty files)."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 5, "empty.txt")
        content = b""
        
        storage.put_object(uri, content)
        retrieved = storage.get_object(uri).read()
        
        assert retrieved == b""
    
    def test_special_characters_in_filename(self, storage, test_workspace_id, test_artifact_id):
        """Filenames with special characters should work."""
        uri = make_storage_uri(test_workspace_id, test_artifact_id, 6, "file-with_special.chars-123.txt")
        content = b"Special filename test"
        
        storage.put_object(uri, content)
        retrieved = storage.get_object(uri).read()
        
        assert retrieved == content


class TestStorageURIStructure:
    """Test the canonical storage URI structure per spec."""
    
    def test_uri_structure_matches_spec(self, storage):
        """Storage URI must match spec: s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/..."""
        workspace_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())
        version = 1
        filename = "document.pdf"
        
        uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/{filename}"
        
        # Should validate successfully
        key = storage._validate_storage_uri(uri)
        
        # Key should contain all components
        assert workspace_id in key
        assert "artifacts" in key
        assert artifact_id in key
        assert f"v{version}" in key
        assert filename in key
    
    def test_nested_paths_supported(self, storage, test_workspace_id, test_artifact_id):
        """Support nested paths within version directory."""
        uri = f"s3://agora/{test_workspace_id}/artifacts/{test_artifact_id}/v1/extracted/page_1.txt"
        content = b"Page 1 extracted text"
        
        storage.put_object(uri, content)
        retrieved = storage.get_object(uri).read()
        
        assert retrieved == content
