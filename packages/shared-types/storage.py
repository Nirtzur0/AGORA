"""
Storage module for AGORA artifact storage.

Implements immutable artifact storage on MinIO/S3 with strict URI structure
and overwrite prevention per spec §7.
"""
import os
import io
from typing import BinaryIO, Union
from urllib.parse import urlparse
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class ObjectExistsError(StorageError):
    """Raised when attempting to overwrite an existing object."""
    pass


class ObjectNotFoundError(StorageError):
    """Raised when requested object does not exist."""
    pass


class InvalidStorageURIError(StorageError):
    """Raised when storage URI doesn't match required structure."""
    pass


class Storage:
    """
    Immutable artifact storage on MinIO/S3.
    
    Enforces:
    - URI structure: s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/...
    - Immutability: objects cannot be overwritten
    - Clean error handling with specific exceptions
    """
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1"
    ):
        """
        Initialize storage client.
        
        Args:
            endpoint: S3/MinIO endpoint URL (e.g., http://localhost:9000)
            access_key: Access key ID
            secret_key: Secret access key
            bucket: Bucket name
            region: AWS region (default: us-east-1)
        """
        self.bucket = bucket
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version='s3v4')
        )
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info(f"Creating bucket: {self.bucket}")
                self.s3.create_bucket(Bucket=self.bucket)
            else:
                raise StorageError(f"Failed to check/create bucket: {e}")
    
    def _validate_storage_uri(self, storage_uri: str) -> str:
        """
        Validate storage URI matches required structure.
        
        Required structure: s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/...
        
        Args:
            storage_uri: Storage URI to validate
            
        Returns:
            Object key (path within bucket)
            
        Raises:
            InvalidStorageURIError: If URI doesn't match required structure
        """
        parsed = urlparse(storage_uri)
        
        # Check scheme
        if parsed.scheme != 's3':
            raise InvalidStorageURIError(f"Invalid scheme '{parsed.scheme}', expected 's3'")
        
        # Check bucket/netloc
        if parsed.netloc != 'agora':
            raise InvalidStorageURIError(f"Invalid bucket '{parsed.netloc}', expected 'agora'")
        
        # Check path structure
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 4:
            raise InvalidStorageURIError(
                f"Invalid path structure. Expected: "
                f"s3://agora/{{workspace_id}}/artifacts/{{artifact_id}}/v{{version}}/..."
            )
        
        # Validate path components
        if path_parts[1] != 'artifacts':
            raise InvalidStorageURIError(
                f"Invalid path: second component must be 'artifacts', got '{path_parts[1]}'"
            )
        
        if not path_parts[3].startswith('v'):
            raise InvalidStorageURIError(
                f"Invalid version component: must start with 'v', got '{path_parts[3]}'"
            )
        
        # Return the key (everything after s3://agora/)
        return parsed.path.lstrip('/')
    
    def put_object(self, storage_uri: str, data: Union[bytes, BinaryIO]) -> None:
        """
        Store an object at the given URI.
        
        Enforces immutability: if object exists, raises ObjectExistsError.
        
        Args:
            storage_uri: Storage URI (must match spec structure)
            data: Bytes or binary stream to store
            
        Raises:
            InvalidStorageURIError: If URI doesn't match required structure
            ObjectExistsError: If object already exists (immutability violation)
            StorageError: On other storage failures
        """
        key = self._validate_storage_uri(storage_uri)
        
        # Check if object already exists (immutability enforcement)
        if self.exists(storage_uri):
            raise ObjectExistsError(
                f"Object already exists at {storage_uri}. "
                f"Storage is immutable - cannot overwrite existing objects."
            )
        
        try:
            if isinstance(data, bytes):
                self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
            else:
                self.s3.upload_fileobj(data, self.bucket, key)
            
            logger.info(f"Stored object: {storage_uri}")
        except ClientError as e:
            raise StorageError(f"Failed to store object: {e}")
    
    def get_object(self, storage_uri: str) -> BinaryIO:
        """
        Retrieve an object from storage.
        
        Args:
            storage_uri: Storage URI (must match spec structure)
            
        Returns:
            Binary stream of object content
            
        Raises:
            InvalidStorageURIError: If URI doesn't match required structure
            ObjectNotFoundError: If object doesn't exist
            StorageError: On other storage failures
        """
        key = self._validate_storage_uri(storage_uri)
        
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            return response['Body']
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise ObjectNotFoundError(f"Object not found: {storage_uri}")
            raise StorageError(f"Failed to retrieve object: {e}")
    
    def exists(self, storage_uri: str) -> bool:
        """
        Check if an object exists in storage.
        
        Args:
            storage_uri: Storage URI (must match spec structure)
            
        Returns:
            True if object exists, False otherwise
            
        Raises:
            InvalidStorageURIError: If URI doesn't match required structure
            StorageError: On storage failures
        """
        key = self._validate_storage_uri(storage_uri)
        
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            raise StorageError(f"Failed to check object existence: {e}")


def create_storage_from_env() -> Storage:
    """
    Create Storage instance from environment variables.
    
    Required env vars:
    - S3_ENDPOINT
    - S3_ACCESS_KEY
    - S3_SECRET_KEY
    - S3_BUCKET
    
    Returns:
        Configured Storage instance
    """
    return Storage(
        endpoint=os.getenv('S3_ENDPOINT', 'http://localhost:9000'),
        access_key=os.getenv('S3_ACCESS_KEY', 'agora'),
        secret_key=os.getenv('S3_SECRET_KEY', 'agora_dev_password'),
        bucket=os.getenv('S3_BUCKET', 'agora'),
    )
