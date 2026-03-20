"""
Sandbox Execution Activity for AGORA Temporal Worker.

Implements sandbox execution per spec §6.4:
- Run script in constrained Docker container
- No network by default
- Resource limits (CPU, memory)
- Capture stdout/stderr as log artifact + version
- Store run config/provenance as artifact metadata

Evidence pointer format: log:char=start-end
"""
import os
import json
import uuid
import logging
import tempfile
import shutil
import subprocess
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path

from search_indexing import upsert_search_index

logger = logging.getLogger(__name__)


class SandboxExecutionError(Exception):
    """Base exception for sandbox execution failures."""
    def __init__(self, message="Sandbox execution failed"):
        self.message = message
        super().__init__(self.message)


class DockerError(SandboxExecutionError):
    """Raised when Docker operations fail."""
    def __init__(self, message="Docker operation failed"):
        super().__init__(message)


class SandboxRunActivity:
    """
    Temporal activity for sandbox execution.
    
    Handles:
    - Docker container creation with constraints
    - Script execution with timeout
    - Log capture (stdout/stderr)
    - Artifact versioning for logs and config
    """
    
    def __init__(self, storage, db):
        """
        Initialize sandbox run activity.
        
        Args:
            storage: MinIO storage client
            db: Database connection wrapper
        """
        self.storage = storage
        self.db = db
    
    def run_sandbox(
        self,
        artifact_id: str,
        workspace_id: str,
        script_artifact_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        created_by: str = "SYSTEM",
        activity_run_id: Optional[str] = None,
        image: str = "python:3.11-slim",
        timeout_seconds: int = 300,
        memory_limit: str = "512m",
        cpu_limit: str = "1.0"
    ) -> Dict[str, Any]:
        """
        Execute script in Docker sandbox.
        
        Args:
            artifact_id: UUID of the log artifact to create
            workspace_id: Workspace UUID
            script_artifact_id: UUID of artifact containing script to execute
            parameters: Optional execution parameters (env vars, args)
            created_by: Agent ID or SYSTEM
            activity_run_id: Optional activity run tracking ID
            image: Docker image to use
            timeout_seconds: Execution timeout
            memory_limit: Container memory limit (e.g., "512m")
            cpu_limit: Container CPU limit (e.g., "1.0")
            
        Returns:
            Dict with artifact_id, version_id, execution metadata
            
        Raises:
            SandboxExecutionError: If execution fails
        """
        logger.info(f"Starting sandbox execution for artifact {artifact_id}")
        
        # Get script content from artifact
        script_content = self._get_script_content(script_artifact_id)
        
        # Prepare execution environment
        temp_dir = tempfile.mkdtemp(prefix="agora_sandbox_")
        
        try:
            # Write script to temp directory
            script_path = Path(temp_dir) / "script.py"
            script_path.write_text(script_content)
            
            # Execute in Docker
            execution_result = self._execute_in_docker(
                script_path=script_path,
                parameters=parameters or {},
                image=image,
                timeout_seconds=timeout_seconds,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                temp_dir=temp_dir
            )
            
            # Store log artifact
            log_content = execution_result["stdout"] + "\n" + execution_result["stderr"]
            version_id = self._store_log_artifact(
                artifact_id=artifact_id,
                workspace_id=workspace_id,
                log_content=log_content,
                execution_metadata=execution_result["metadata"],
                created_by=created_by
            )
            
            # Store execution config as artifact metadata
            config_artifact_id = str(uuid.uuid4())
            self._store_config_artifact(
                artifact_id=config_artifact_id,
                workspace_id=workspace_id,
                script_artifact_id=script_artifact_id,
                parameters=parameters or {},
                image=image,
                timeout_seconds=timeout_seconds,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                created_by=created_by
            )
            
            # Log execution
            self._log_execution(
                workspace_id=workspace_id,
                artifact_id=artifact_id,
                version_id=version_id,
                script_artifact_id=script_artifact_id,
                exit_code=execution_result["exit_code"],
                activity_run_id=activity_run_id,
                created_by=created_by
            )
            
            return {
                "artifact_id": artifact_id,
                "version_id": version_id,
                "config_artifact_id": config_artifact_id,
                "exit_code": execution_result["exit_code"],
                "stdout_length": len(execution_result["stdout"]),
                "stderr_length": len(execution_result["stderr"]),
                "execution_time_seconds": execution_result["metadata"]["execution_time_seconds"]
            }
            
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _get_script_content(self, script_artifact_id: str) -> str:
        """
        Retrieve script content from artifact.
        
        Args:
            script_artifact_id: UUID of script artifact
            
        Returns:
            Script content as string
            
        Raises:
            SandboxExecutionError: If script not found or cannot be retrieved
        """
        # Get latest version of script artifact
        result = self.db.execute(
            """
            SELECT av.id, av.version, av.storage_uri
            FROM artifacts a
            JOIN artifact_versions av ON a.id = av.artifact_id
            WHERE a.id = :artifact_id
            ORDER BY av.version DESC
            LIMIT 1
            """,
            {"artifact_id": script_artifact_id}
        ).fetchone()
        
        if not result:
            raise SandboxExecutionError(f"Script artifact {script_artifact_id} not found")
        
        version_id, version_number, storage_uri = result
        
        # Download from MinIO
        try:
            # storage_uri should point directly to the script object
            response = self.storage.get_object(storage_uri)
            content = response.read().decode("utf-8")
            return content
            
        except Exception as e:
            raise SandboxExecutionError(f"Failed to download script: {str(e)}")
    
    def _execute_in_docker(
        self,
        script_path: Path,
        parameters: Dict[str, Any],
        image: str,
        timeout_seconds: int,
        memory_limit: str,
        cpu_limit: str,
        temp_dir: str
    ) -> Dict[str, Any]:
        """
        Execute script in Docker container with constraints.
        
        Args:
            script_path: Path to script file
            parameters: Execution parameters (env vars, args)
            image: Docker image
            timeout_seconds: Execution timeout
            memory_limit: Memory limit
            cpu_limit: CPU limit
            temp_dir: Temporary directory for mounting
            
        Returns:
            Dict with stdout, stderr, exit_code, metadata
            
        Raises:
            DockerError: If Docker execution fails
        """
        # Build Docker command
        docker_cmd = [
            "docker", "run",
            "--rm",  # Remove container after execution
            "--network", "none",  # No network access
            "--memory", memory_limit,
            "--cpus", cpu_limit,
            "--security-opt", "no-new-privileges",  # Additional security
            "-v", f"{temp_dir}:/workspace:ro",  # Mount as read-only
            "-w", "/workspace",
            image,
            "python", "script.py"
        ]
        
        # Add environment variables from parameters
        if "env" in parameters:
            for key, value in parameters["env"].items():
                docker_cmd.insert(3, "-e")
                docker_cmd.insert(4, f"{key}={value}")
        
        # Add arguments from parameters
        if "args" in parameters:
            docker_cmd.extend(parameters["args"])
        
        logger.info(f"Executing Docker command: {' '.join(docker_cmd)}")
        
        # Execute with timeout
        start_time = datetime.now(timezone.utc)
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False  # Don't raise on non-zero exit
            )
            
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds()
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "metadata": {
                    "execution_time_seconds": execution_time,
                    "image": image,
                    "memory_limit": memory_limit,
                    "cpu_limit": cpu_limit,
                    "timeout_seconds": timeout_seconds,
                    "started_at": start_time.isoformat(),
                    "completed_at": end_time.isoformat()
                }
            }
            
        except subprocess.TimeoutExpired as e:
            raise DockerError(f"Execution timed out after {timeout_seconds} seconds")
        except FileNotFoundError:
            raise DockerError("Docker not found. Ensure Docker is installed and in PATH.")
        except Exception as e:
            raise DockerError(f"Docker execution failed: {str(e)}")
    
    def _store_log_artifact(
        self,
        artifact_id: str,
        workspace_id: str,
        log_content: str,
        execution_metadata: Dict[str, Any],
        created_by: str
    ) -> str:
        """
        Store log artifact and create version.
        
        Args:
            artifact_id: Log artifact UUID
            workspace_id: Workspace UUID
            log_content: Combined stdout/stderr
            execution_metadata: Execution metadata
            created_by: Creator ID
            
        Returns:
            Version ID
        """
        # Store log in MinIO
        version_id = str(uuid.uuid4())
        result = self.db.execute(
            """
            SELECT COALESCE(MAX(version) + 1, 1)
            FROM artifact_versions
            WHERE artifact_id = :artifact_id
            """,
            {"artifact_id": artifact_id}
        ).fetchone()
        version_number = result[0] if result else 1
        storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version_number}/log.txt"
        
        try:
            log_bytes = log_content.encode('utf-8')
            self.storage.put_object(storage_uri, log_bytes)
        except Exception as e:
            raise SandboxExecutionError(f"Failed to store log artifact: {str(e)}")
        
        # Create artifact_versions row
        import hashlib
        content_hash = hashlib.sha256(log_content.encode('utf-8')).hexdigest()
        
        self.db.execute(
            """
            INSERT INTO artifact_versions (
                id, artifact_id, version, storage_uri, content_hash, created_by, created_at
            )
            VALUES (
                :id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW()
            )
            """,
            {
                "id": version_id,
                "artifact_id": artifact_id,
                "version": version_number,
                "content_hash": content_hash,
                "storage_uri": storage_uri,
                "created_by": created_by
            }
        )

        upsert_search_index(
            workspace_id=workspace_id,
            artifact_id=artifact_id,
            artifact_version_id=version_id,
            artifact_type="log",
            search_text=log_content,
            metadata=execution_metadata,
            db=self.db,
        )
        
        self.db.commit()
        
        return version_id
    
    def _store_config_artifact(
        self,
        artifact_id: str,
        workspace_id: str,
        script_artifact_id: str,
        parameters: Dict[str, Any],
        image: str,
        timeout_seconds: int,
        memory_limit: str,
        cpu_limit: str,
        created_by: str
    ) -> str:
        """
        Store execution config as artifact.
        
        Args:
            artifact_id: Config artifact UUID
            workspace_id: Workspace UUID
            script_artifact_id: Script artifact UUID
            parameters: Execution parameters
            image: Docker image
            timeout_seconds: Timeout
            memory_limit: Memory limit
            cpu_limit: CPU limit
            created_by: Creator ID
            
        Returns:
            Config artifact ID
        """
        config = {
            "script_artifact_id": script_artifact_id,
            "parameters": parameters,
            "image": image,
            "timeout_seconds": timeout_seconds,
            "memory_limit": memory_limit,
            "cpu_limit": cpu_limit,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        config_json = json.dumps(config, indent=2)
        storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/"
        
        # Create artifact
        self.db.execute(
            """
            INSERT INTO artifacts (id, workspace_id, short_id, type, metadata, storage_uri, created_by, created_at)
            VALUES (:id, :workspace_id, :short_id, :type, :metadata, :storage_uri, :created_by, NOW())
            """,
            {
                "id": artifact_id,
                "workspace_id": workspace_id,
                "short_id": f"CFG{abs(hash(artifact_id)) % 10000}",
                "type": "config",
                "metadata": json.dumps({"purpose": "sandbox_execution_config"}),
                "storage_uri": storage_uri,
                "created_by": created_by
            }
        )
        
        # Store config in MinIO
        version_id = str(uuid.uuid4())
        version_number = 1
        config_storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version_number}/config.json"
        
        try:
            config_bytes = config_json.encode('utf-8')
            self.storage.put_object(config_storage_uri, config_bytes)
        except Exception as e:
            raise SandboxExecutionError(f"Failed to store config artifact: {str(e)}")
        
        # Create version
        import hashlib
        content_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()
        
        self.db.execute(
            """
            INSERT INTO artifact_versions (
                id, artifact_id, version, storage_uri, content_hash, created_by, created_at
            )
            VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, NOW())
            """,
            {
                "id": version_id,
                "artifact_id": artifact_id,
                "version": version_number,
                "content_hash": content_hash,
                "storage_uri": config_storage_uri,
                "created_by": created_by
            }
        )
        
        self.db.commit()
        
        return artifact_id
    
    def _log_execution(
        self,
        workspace_id: str,
        artifact_id: str,
        version_id: str,
        script_artifact_id: str,
        exit_code: int,
        activity_run_id: Optional[str],
        created_by: str
    ):
        """
        Write execution log entry.
        
        Args:
            workspace_id: Workspace UUID
            artifact_id: Log artifact UUID
            version_id: Version UUID
            script_artifact_id: Script artifact UUID
            exit_code: Process exit code
            activity_run_id: Activity run ID
            created_by: Creator ID
        """
        log_entry = {
            "event": "sandbox_execution",
            "artifact_id": artifact_id,
            "version_id": version_id,
            "script_artifact_id": script_artifact_id,
            "exit_code": exit_code,
            "activity_run_id": activity_run_id
        }
        
        self.db.execute(
            """
            INSERT INTO logs (id, workspace_id, agent_id, action, payload, created_at)
            VALUES (:id, :workspace_id, :agent_id, :action, :payload, NOW())
            """,
            {
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "agent_id": created_by if created_by != "SYSTEM" else None,
                "action": "sandbox.execution",
                "payload": log_entry
            }
        )
        
        self.db.commit()
    
    @staticmethod
    def resolve_log_evidence(
        artifact_version_id: str,
        location: str,
        db
    ) -> str:
        """
        Resolve log evidence pointer to text snippet.
        
        Args:
            artifact_version_id: UUID of log artifact version
            location: Evidence location (log:char=start-end)
            db: Database connection
            
        Returns:
            Text snippet from log
            
        Raises:
            ValueError: If location format invalid or artifact not found
        """
        # Parse location
        if not location.startswith("log:char="):
            raise ValueError(f"Invalid log location format: {location}")
        
        char_spec = location[9:]  # Remove "log:char=" prefix
        
        try:
            if '-' in char_spec:
                start, end = char_spec.split('-')
                start = int(start)
                end = int(end)
            else:
                raise ValueError("Log location must specify range: char=start-end")
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid char range in location '{location}': {e}")
        
        # Get artifact version
        result = db.execute(
            """
            SELECT av.storage_uri, av.id
            FROM artifact_versions av
            WHERE av.id = :version_id
            """,
            {"version_id": artifact_version_id}
        ).fetchone()
        
        if not result:
            raise ValueError(f"Artifact version {artifact_version_id} not found")
        
        storage_uri, version_id = result
        
        # Download log from storage
        from storage import create_storage_from_env
        storage = create_storage_from_env()
        
        try:
            response = storage.get_object(storage_uri)
            log_content = response.read().decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to retrieve log content: {str(e)}")
        
        # Extract requested range
        if start < 0 or end > len(log_content) or start >= end:
            raise ValueError(f"Invalid char range {start}-{end} for log length {len(log_content)}")
        
        return log_content[start:end]
