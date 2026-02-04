"""
Repo Ingestion Activity for AGORA Temporal Worker.

Implements repo ingestion per spec §6.2:
- git clone (or accept zip)
- pin snapshot (commit hash in metadata)
- store snapshot in MinIO
- store file list for indexing/retrieval
- create artifact_versions row
- write logs + activity_runs

Evidence pointer format: repo:path={path}#L{start}-L{end}
"""
import os
import re
import json
import hashlib
import tempfile
import shutil
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from uuid import uuid4
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RepoIngestionError(Exception):
    """Base exception for repo ingestion failures."""
    def __init__(self, message="Repo ingestion failed"):
        self.message = message
        super().__init__(self.message)


class GitCloneError(RepoIngestionError):
    """Raised when git clone fails."""
    def __init__(self, message="Git clone failed"):
        super().__init__(message)


class RepoIngestActivity:
    """
    Temporal activity for repository ingestion.
    
    Handles:
    - Git clone from URL
    - Commit hash pinning
    - File tree indexing
    - Storage in MinIO
    - Artifact version creation
    """
    
    def __init__(self, storage, db):
        """
        Initialize repo ingestion activity.
        
        Args:
            storage: Storage instance for MinIO operations
            db: Database connection for artifact_versions/logs
        """
        self.storage = storage
        self.db = db
        
        # Verify git is available
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("git CLI not available. Install git.")
    
    def ingest_repo(
        self,
        artifact_id: str,
        workspace_id: str,
        repo_url: str,
        created_by: str,
        branch: Optional[str] = None,
        commit_hash: Optional[str] = None,
        activity_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest repository: clone -> snapshot -> index -> store.
        
        Args:
            artifact_id: Artifact UUID
            workspace_id: Workspace UUID
            repo_url: Git repository URL
            created_by: Agent UUID who initiated ingestion
            branch: Optional branch to clone (default: main/master)
            commit_hash: Optional specific commit to pin
            activity_run_id: Optional activity run ID for logging
            
        Returns:
            Dict with artifact_version_id, version, commit_hash, file_count, storage_uris
            
        Raises:
            GitCloneError: If git clone fails
            RepoIngestionError: On other ingestion failures
        """
        logger.info(f"Starting repo ingestion for artifact {artifact_id} from {repo_url}")
        
        temp_dir = None
        try:
            # Get next version number
            result = self.db.execute(
                """
                SELECT MAX(version) FROM artifact_versions WHERE artifact_id = :artifact_id
                """,
                {"artifact_id": artifact_id}
            )
            max_version = result.fetchone()[0]
            next_version = (max_version or 0) + 1
            
            # Clone repo to temp directory
            temp_dir = tempfile.mkdtemp(prefix="agora_repo_")
            logger.info(f"Cloning to temporary directory: {temp_dir}")
            
            clone_commit = self._clone_repo(repo_url, temp_dir, branch, commit_hash)
            
            # Index files (exclude .git directory)
            file_list = self._index_repo_files(temp_dir)
            logger.info(f"Indexed {len(file_list)} files from repository")
            
            # Store snapshot in MinIO
            storage_uris = self._store_repo_snapshot(
                workspace_id, artifact_id, next_version, temp_dir, file_list
            )
            
            # Store file index metadata
            metadata = {
                "repo_url": repo_url,
                "commit_hash": clone_commit,
                "branch": branch,
                "file_count": len(file_list),
                "files": file_list,  # List of {path, size, lines} dicts
                "cloned_at": datetime.utcnow().isoformat()
            }
            metadata_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{next_version}/metadata.json"
            self.storage.put_object(metadata_uri, json.dumps(metadata, indent=2).encode('utf-8'))
            
            # Create artifact_versions row
            version_id = uuid4()
            self.db.execute(
                """
                INSERT INTO artifact_versions (id, artifact_id, version, storage_uri, content_hash, created_by, created_at)
                VALUES (:id, :artifact_id, :version, :storage_uri, :content_hash, :created_by, :created_at)
                """,
                {
                    "id": str(version_id),
                    "artifact_id": artifact_id,
                    "version": next_version,
                    "storage_uri": metadata_uri,  # Primary URI points to metadata
                    "content_hash": clone_commit,  # Use commit hash as content hash
                    "created_by": created_by,
                    "created_at": datetime.utcnow()
                }
            )
            
            # Write success log
            self._write_log(
                workspace_id, created_by, "repo.ingestion_completed",
                {
                    "artifact_id": artifact_id,
                    "artifact_version_id": str(version_id),
                    "version": next_version,
                    "repo_url": repo_url,
                    "commit_hash": clone_commit,
                    "file_count": len(file_list)
                }
            )
            
            self.db.commit()
            
            logger.info(f"Repo ingestion completed: version_id={version_id}, commit={clone_commit}, files={len(file_list)}")
            
            return {
                "artifact_version_id": str(version_id),
                "version": next_version,
                "commit_hash": clone_commit,
                "file_count": len(file_list),
                "metadata_uri": metadata_uri,
                "storage_uris": storage_uris
            }
            
        except GitCloneError:
            raise
        except Exception as e:
            error_msg = f"Repo ingestion failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._write_log(
                workspace_id, created_by, "repo.ingestion_failed",
                {"artifact_id": artifact_id, "repo_url": repo_url, "error": error_msg}
            )
            raise RepoIngestionError(error_msg) from e
        finally:
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
    
    def _clone_repo(
        self,
        repo_url: str,
        target_dir: str,
        branch: Optional[str] = None,
        commit_hash: Optional[str] = None
    ) -> str:
        """
        Clone repository and return pinned commit hash.
        
        Args:
            repo_url: Git repository URL
            target_dir: Directory to clone into
            branch: Optional branch to clone
            commit_hash: Optional specific commit to checkout
            
        Returns:
            Commit hash of cloned/checked out state
            
        Raises:
            GitCloneError: If clone or checkout fails
        """
        try:
            # Clone with depth=1 for efficiency unless specific commit requested
            clone_cmd = ["git", "clone"]
            
            if not commit_hash:
                clone_cmd.extend(["--depth", "1"])
            
            if branch:
                clone_cmd.extend(["--branch", branch])
            
            clone_cmd.extend([repo_url, target_dir])
            
            result = subprocess.run(
                clone_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                error_msg = f"Git clone failed: {result.stderr}"
                logger.error(error_msg)
                raise GitCloneError(error_msg)
            
            # If specific commit requested, checkout that commit
            if commit_hash:
                checkout_result = subprocess.run(
                    ["git", "checkout", commit_hash],
                    cwd=target_dir,
                    capture_output=True,
                    text=True
                )
                if checkout_result.returncode != 0:
                    raise GitCloneError(f"Git checkout failed: {checkout_result.stderr}")
            
            # Get current commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            current_commit = hash_result.stdout.strip()
            logger.info(f"Cloned repo at commit: {current_commit}")
            
            return current_commit
            
        except subprocess.TimeoutExpired:
            raise GitCloneError(f"Git clone timed out after 300s")
        except subprocess.CalledProcessError as e:
            raise GitCloneError(f"Git command failed: {e}")
        except Exception as e:
            raise GitCloneError(f"Clone failed: {str(e)}")
    
    def _index_repo_files(self, repo_dir: str) -> List[Dict[str, Any]]:
        """
        Index all files in repository (excluding .git).
        
        Args:
            repo_dir: Path to cloned repository
            
        Returns:
            List of dicts with {path, size, lines, is_text}
        """
        files = []
        repo_path = Path(repo_dir)
        
        for file_path in repo_path.rglob("*"):
            # Skip .git directory and non-files
            if ".git" in file_path.parts or not file_path.is_file():
                continue
            
            rel_path = file_path.relative_to(repo_path)
            
            # Get file stats
            size = file_path.stat().st_size
            
            # Try to determine if text file and count lines
            is_text, line_count = self._analyze_file(file_path)
            
            files.append({
                "path": str(rel_path),
                "size": size,
                "lines": line_count if is_text else None,
                "is_text": is_text
            })
        
        return files
    
    def _analyze_file(self, file_path: Path) -> Tuple[bool, Optional[int]]:
        """
        Analyze if file is text and count lines.
        
        Returns:
            (is_text, line_count or None)
        """
        try:
            # Try to read as text
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = 0
                for _ in f:
                    lines += 1
                return True, lines
        except (UnicodeDecodeError, IsADirectoryError):
            return False, None
    
    def _store_repo_snapshot(
        self,
        workspace_id: str,
        artifact_id: str,
        version: int,
        repo_dir: str,
        file_list: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Store repository snapshot files in MinIO.
        
        Args:
            workspace_id: Workspace UUID
            artifact_id: Artifact UUID
            version: Version number
            repo_dir: Path to cloned repository
            file_list: List of indexed files
            
        Returns:
            Dict mapping file paths to storage URIs
        """
        storage_uris = {}
        repo_path = Path(repo_dir)
        
        for file_info in file_list:
            file_path = file_info["path"]
            full_path = repo_path / file_path
            
            # Store file in MinIO
            storage_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/files/{file_path}"
            
            with open(full_path, 'rb') as f:
                file_bytes = f.read()
            
            self.storage.put_object(storage_uri, file_bytes)
            storage_uris[file_path] = storage_uri
        
        logger.info(f"Stored {len(storage_uris)} files in MinIO")
        return storage_uris
    
    def resolve_repo_evidence(
        self,
        artifact_version_id: str,
        location: str
    ) -> Dict[str, Any]:
        """
        Resolve repo evidence pointer: repo:path={path}#L{start}-L{end}
        
        Args:
            artifact_version_id: Artifact version UUID
            location: Location string (e.g., "repo:path=src/main.py#L10-L20")
            
        Returns:
            Dict with ok, snippet, normalized_location, or error
        """
        # Parse location format
        match = re.match(r"repo:path=([^#]+)#L(\d+)-L(\d+)", location)
        if not match:
            return {
                "ok": False,
                "code": "INVALID_LOCATION_FORMAT",
                "message": f"Invalid repo location format: {location}. Expected: repo:path=<path>#L<start>-L<end>"
            }
        
        file_path = match.group(1)
        start_line = int(match.group(2))
        end_line = int(match.group(3))
        
        if start_line < 1 or end_line < start_line:
            return {
                "ok": False,
                "code": "INVALID_LINE_RANGE",
                "message": f"Invalid line range: L{start_line}-L{end_line}"
            }
        
        try:
            # Get artifact_version to find storage URI
            result = self.db.execute(
                """
                SELECT av.storage_uri, av.artifact_id, a.workspace_id
                FROM artifact_versions av
                JOIN artifacts a ON av.artifact_id = a.id
                WHERE av.id = :version_id
                """,
                {"version_id": artifact_version_id}
            )
            row = result.fetchone()
            
            if not row:
                return {
                    "ok": False,
                    "code": "ARTIFACT_VERSION_NOT_FOUND",
                    "message": f"Artifact version {artifact_version_id} not found"
                }
            
            metadata_uri, artifact_id, workspace_id = row
            
            # Load metadata to get file info
            metadata_bytes = self.storage.get_object(metadata_uri).read()
            metadata = json.loads(metadata_bytes.decode("utf-8"))
            
            # Check if file exists in repo
            file_info = next((f for f in metadata["files"] if f["path"] == file_path), None)
            if not file_info:
                return {
                    "ok": False,
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {file_path} not found in repository"
                }
            
            if not file_info["is_text"]:
                return {
                    "ok": False,
                    "code": "NON_TEXT_FILE",
                    "message": f"File {file_path} is not a text file"
                }
            
            # Check line range validity
            total_lines = file_info.get("lines", 0)
            if end_line > total_lines:
                return {
                    "ok": False,
                    "code": "LINE_OUT_OF_RANGE",
                    "message": f"Line range L{start_line}-L{end_line} exceeds file length ({total_lines} lines)"
                }
            
            # Load file content
            version = metadata.get("version", 1)
            file_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/files/{file_path}"
            
            file_bytes = self.storage.get_object(file_uri).read()
            file_content = file_bytes.decode("utf-8")
            
            # Extract line range
            lines = file_content.splitlines()
            snippet_lines = lines[start_line - 1:end_line]  # 1-indexed to 0-indexed
            snippet = "\n".join(snippet_lines)
            
            return {
                "ok": True,
                "artifact_version_id": artifact_version_id,
                "normalized_location": f"repo:path={file_path}#L{start_line}-L{end_line}",
                "mime": "text/plain",
                "snippet": snippet,
                "source": {
                    "file_path": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "commit_hash": metadata.get("commit_hash"),
                    "repo_url": metadata.get("repo_url")
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to resolve repo evidence: {e}", exc_info=True)
            return {
                "ok": False,
                "code": "RESOLUTION_ERROR",
                "message": str(e)
            }
    
    def read_file_from_repo(
        self,
        artifact_version_id: str,
        file_path: str
    ) -> str:
        """
        Read a file from a stored repo snapshot.
        
        Args:
            artifact_version_id: UUID of repo artifact version
            file_path: Path to file within repo
            
        Returns:
            File content as string
            
        Raises:
            ValueError: If artifact not found or file doesn't exist
        """
        # Get artifact details
        result = self.db.execute(
            """
            SELECT av.storage_uri, av.content_hash, a.workspace_id, a.id
            FROM artifact_versions av
            JOIN artifacts a ON av.artifact_id = a.id
            WHERE av.id = :version_id
            """,
            {"version_id": artifact_version_id}
        ).fetchone()
        
        if not result:
            raise ValueError(f"Artifact version {artifact_version_id} not found")
        
        storage_uri, commit_hash, workspace_id, artifact_id = result
        
        # Retrieve file directly from stored snapshot
        base_uri = storage_uri.rsplit("/", 1)[0]
        file_uri = f"{base_uri}/files/{file_path}"
        
        try:
            response = self.storage.get_object(file_uri)
            return response.read().decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to retrieve file '{file_path}' from repo snapshot: {str(e)}")
    
    def _write_log(
        self,
        workspace_id: str,
        agent_id: str,
        action: str,
        payload: Dict[str, Any]
    ):
        """Write audit log entry."""
        try:
            self.db.execute(
                """
                INSERT INTO logs (id, workspace_id, agent_id, action, payload, created_at)
                VALUES (:id, :workspace_id, :agent_id, :action, :payload, :created_at)
                """,
                {
                    "id": str(uuid4()),
                    "workspace_id": workspace_id,
                    "agent_id": agent_id,
                    "action": action,
                    "payload": json.dumps(payload),
                    "created_at": datetime.utcnow()
                }
            )
        except Exception as e:
            logger.error(f"Failed to write log: {e}")
