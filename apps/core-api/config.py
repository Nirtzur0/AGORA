"""Core API configuration using the canonical runtime environment contract."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from runtime_config import (
    get_agent_jwt_secret,
    get_core_api_port,
    get_system_jwt_audience,
    get_system_jwt_secret,
    get_temporal_address,
    get_temporal_task_queue,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = (
        f"postgresql://agora:agora_dev_password@localhost:{os.getenv('AGORA_DB_PORT', '55432')}/agora"
    )
    
    # Object Storage (MinIO/S3)
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "agora"
    s3_secret_key: str = "agora_dev_password"
    s3_bucket: str = "agora"
    
    # Temporal
    temporal_address: str = get_temporal_address()
    temporal_namespace: str = "default"
    temporal_task_queue: str = get_temporal_task_queue()
    
    # Moltbook Adapter
    moltbook_adapter_url: str = "http://localhost:3001"
    
    # JWT
    jwt_secret_key: str = get_agent_jwt_secret()
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours
    
    # Service JWT (system-only auth)
    service_jwt_secret_key: str = get_system_jwt_secret()
    service_jwt_audience: str = get_system_jwt_audience()
    
    # API
    api_title: str = "AGORA Core API"
    api_version: str = "1.0.0"
    api_debug: bool = False
    api_port: int = get_core_api_port()
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
