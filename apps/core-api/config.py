"""
Core API configuration using environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://agora:agora_dev_password@localhost:5432/agora"
    
    # Object Storage (MinIO/S3)
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "agora"
    s3_secret_key: str = "agora_dev_password"
    s3_bucket: str = "agora"
    
    # Temporal
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "agora-tasks"
    
    # Moltbook Adapter
    moltbook_adapter_url: str = "http://localhost:3001"
    
    # JWT
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours
    
    # Service JWT (system-only auth)
    service_jwt_secret_key: str = "dev-service-secret-change-in-production"
    service_jwt_audience: str = "agora-internal"
    
    # API
    api_title: str = "AGORA Core API"
    api_version: str = "1.0.0"
    api_debug: bool = False
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
