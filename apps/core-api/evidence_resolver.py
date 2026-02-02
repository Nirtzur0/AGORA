"""
Evidence Pointer Resolver - Component 10

Canonical resolver for evidence pointers per Docs/04 §5.8.
All citation checks, claim-evidence validation, and UI evidence display
MUST use this resolver to ensure deterministic resolution.

Supported location formats:
- pdf:p={page}#char={start}-{end}
- repo:path={path}#L{start}-L{end}
- log:jsonpath={jsonpath}
- log:char={start}-{end}

Returns:
- Success: {ok: true, snippet: "...", normalized_location: "...", ...}
- Error: {ok: false, code: "...", message: "..."}
"""
import re
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import jsonpath_ng


@dataclass
class ResolverResult:
    """Result of evidence pointer resolution."""
    ok: bool
    artifact_version_id: str
    normalized_location: Optional[str] = None
    mime: Optional[str] = None
    snippet: Optional[str] = None
    source: Optional[Dict[str, Any]] = None
    # Error fields
    code: Optional[str] = None
    message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        if self.ok:
            return {
                "ok": True,
                "artifact_version_id": self.artifact_version_id,
                "normalized_location": self.normalized_location,
                "mime": self.mime,
                "snippet": self.snippet,
                "source": self.source
            }
        else:
            return {
                "ok": False,
                "code": self.code,
                "message": self.message
            }


class EvidenceResolver:
    """
    Canonical evidence pointer resolver.
    
    This class is the single source of truth for evidence resolution.
    Used by:
    - GET /evidence/resolve endpoint (agent + UI)
    - citation_check validation
    - claim-evidence validation
    - draft citation coverage checks
    """
    
    def __init__(self, storage, db):
        """
        Initialize resolver with storage and database access.
        
        Args:
            storage: Storage interface (MinIO/S3)
            db: Database session
        """
        self.storage = storage
        self.db = db
    
    def resolve(
        self,
        artifact_version_id: str,
        location: str
    ) -> ResolverResult:
        """
        Resolve an evidence pointer to a text snippet.
        
        Args:
            artifact_version_id: UUID of artifact_versions.id
            location: Location string (pdf:..., repo:..., log:...)
        
        Returns:
            ResolverResult with ok=True and snippet, or ok=False with error
        """
        # Validate artifact_version exists
        from database import ArtifactVersion
        
        version = self.db.query(ArtifactVersion).filter_by(id=artifact_version_id).first()
        if not version:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="ARTIFACT_VERSION_NOT_FOUND",
                message=f"Artifact version {artifact_version_id} not found"
            )
        
        # Parse location format
        try:
            if location.startswith("pdf:"):
                return self._resolve_pdf(artifact_version_id, location, version)
            elif location.startswith("repo:"):
                return self._resolve_repo(artifact_version_id, location, version)
            elif location.startswith("log:"):
                return self._resolve_log(artifact_version_id, location, version)
            else:
                return ResolverResult(
                    ok=False,
                    artifact_version_id=artifact_version_id,
                    code="UNSUPPORTED_LOCATION",
                    message=f"Unsupported location format: {location}"
                )
        except Exception as e:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="RESOLUTION_ERROR",
                message=str(e)
            )
    
    def _resolve_pdf(
        self,
        artifact_version_id: str,
        location: str,
        version
    ) -> ResolverResult:
        """
        Resolve PDF evidence pointer: pdf:p={page}#char={start}-{end}
        
        Uses the PDF ingestion worker's resolve_pdf_evidence logic.
        """
        # Import PDF activity for resolution
        import sys
        sys.path.insert(0, "/Users/nirtzur/Documents/projects/AGORA/apps/worker")
        from pdf_ingest import PDFIngestActivity
        
        # Create activity instance
        pdf_activity = PDFIngestActivity(self.storage, self.db)
        
        # Parse location format
        match = re.match(r"pdf:p=(\d+)#char=(\d+)-(\d+)", location)
        if not match:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="INVALID_LOCATION_FORMAT",
                message=f"Invalid PDF location format: {location}. Expected: pdf:p={{page}}#char={{start}}-{{end}}"
            )
        
        page = int(match.group(1))
        start_char = int(match.group(2))
        end_char = int(match.group(3))
        
        # Validate page is 1-based
        if page < 1:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="PAGE_OUT_OF_RANGE",
                message=f"Page {page} is invalid (pages are 1-based)"
            )
        
        # Validate char range
        if start_char < 0 or end_char < start_char:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="CHAR_RANGE_INVALID",
                message=f"Invalid char range: {start_char}-{end_char}"
            )
        
        # Get workspace_id from artifact
        from database import Artifact
        artifact = self.db.query(Artifact).filter_by(id=version.artifact_id).first()
        if not artifact:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="ARTIFACT_NOT_FOUND",
                message=f"Artifact {version.artifact_id} not found"
            )
        
        # Resolve using PDF activity
        try:
            snippet = pdf_activity.resolve_pdf_evidence(
                workspace_id=artifact.workspace_id,
                artifact_version_id=artifact_version_id,
                location=location
            )
            
            return ResolverResult(
                ok=True,
                artifact_version_id=artifact_version_id,
                normalized_location=location,  # Already normalized
                mime="text/plain",
                snippet=snippet,
                source={
                    "artifact_id": version.artifact_id,
                    "type": "pdf",
                    "version": version.version
                }
            )
        except FileNotFoundError as e:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="PAGE_OUT_OF_RANGE",
                message=str(e)
            )
        except ValueError as e:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="CHAR_RANGE_INVALID",
                message=str(e)
            )
    
    def _resolve_repo(
        self,
        artifact_version_id: str,
        location: str,
        version
    ) -> ResolverResult:
        """
        Resolve repository evidence pointer: repo:path={path}#L{start}-L{end}
        
        Lines are 1-based.
        Uses RepoIngestActivity for resolution logic.
        """
        # Import repo activity for resolution
        import sys
        sys.path.insert(0, "/Users/nirtzur/Documents/projects/AGORA/apps/worker")
        from repo_ingest import RepoIngestActivity
        
        # Create activity instance
        repo_activity = RepoIngestActivity(self.storage, self.db)
        
        # Use repo activity's resolution method
        result_dict = repo_activity.resolve_repo_evidence(artifact_version_id, location)
        
        # Convert dict result to ResolverResult
        if result_dict.get("ok"):
            return ResolverResult(
                ok=True,
                artifact_version_id=artifact_version_id,
                normalized_location=result_dict["normalized_location"],
                mime=result_dict["mime"],
                snippet=result_dict["snippet"],
                source=result_dict["source"]
            )
        else:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code=result_dict["code"],
                message=result_dict["message"]
            )
    
    def _resolve_log(
        self,
        artifact_version_id: str,
        location: str,
        version
    ) -> ResolverResult:
        """
        Resolve log evidence pointer:
        - log:jsonpath={jsonpath} (for JSON logs)
        - log:char={start}-{end} (for plain-text logs)
        """
        # Get workspace_id from artifact
        from database import Artifact
        artifact = self.db.query(Artifact).filter_by(id=version.artifact_id).first()
        if not artifact:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="ARTIFACT_NOT_FOUND",
                message=f"Artifact {version.artifact_id} not found"
            )
        
        # Check if it's jsonpath or char range
        if location.startswith("log:jsonpath="):
            return self._resolve_log_jsonpath(artifact_version_id, location, version, artifact)
        elif location.startswith("log:char="):
            return self._resolve_log_char(artifact_version_id, location, version, artifact)
        else:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="INVALID_LOCATION_FORMAT",
                message=f"Invalid log location format: {location}. Expected: log:jsonpath={{path}} or log:char={{start}}-{{end}}"
            )
    
    def _resolve_log_jsonpath(
        self,
        artifact_version_id: str,
        location: str,
        version,
        artifact
    ) -> ResolverResult:
        """Resolve JSON log with jsonpath."""
        # Parse jsonpath
        jsonpath_str = location[len("log:jsonpath="):]
        
        # Get log content from storage
        log_key = f"{artifact.workspace_id}/artifacts/{version.artifact_id}/v{version.version}/log.json"
        
        try:
            log_content = self.storage.get_object("agora", log_key).decode("utf-8")
        except Exception:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="ARTIFACT_NOT_FOUND",
                message=f"Log file not found"
            )
        
        # Parse JSON
        try:
            log_data = json.loads(log_content)
        except json.JSONDecodeError as e:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="INVALID_LOG_FORMAT",
                message=f"Log is not valid JSON: {str(e)}"
            )
        
        # Apply jsonpath
        try:
            jsonpath_expr = jsonpath_ng.parse(jsonpath_str)
            matches = jsonpath_expr.find(log_data)
            
            if not matches:
                return ResolverResult(
                    ok=False,
                    artifact_version_id=artifact_version_id,
                    code="JSONPATH_NOT_FOUND",
                    message=f"JSONPath {jsonpath_str} did not match any values"
                )
            
            # Return first match value as snippet
            snippet = json.dumps(matches[0].value, indent=2)
            
            return ResolverResult(
                ok=True,
                artifact_version_id=artifact_version_id,
                normalized_location=location,
                mime="application/json",
                snippet=snippet,
                source={
                    "artifact_id": version.artifact_id,
                    "type": "log",
                    "version": version.version
                }
            )
        except Exception as e:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="JSONPATH_ERROR",
                message=f"Error evaluating JSONPath: {str(e)}"
            )
    
    def _resolve_log_char(
        self,
        artifact_version_id: str,
        location: str,
        version,
        artifact
    ) -> ResolverResult:
        """Resolve plain-text log with char range."""
        # Parse char range
        match = re.match(r"log:char=(\d+)-(\d+)", location)
        if not match:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="INVALID_LOCATION_FORMAT",
                message=f"Invalid log char format: {location}"
            )
        
        start_char = int(match.group(1))
        end_char = int(match.group(2))
        
        # Validate char range
        if start_char < 0 or end_char < start_char:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="CHAR_RANGE_INVALID",
                message=f"Invalid char range: {start_char}-{end_char}"
            )
        
        # Get log content from storage
        log_key = f"{artifact.workspace_id}/artifacts/{version.artifact_id}/v{version.version}/log.txt"
        
        try:
            log_content = self.storage.get_object("agora", log_key).decode("utf-8")
        except Exception:
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="ARTIFACT_NOT_FOUND",
                message=f"Log file not found"
            )
        
        # Validate char range
        if end_char > len(log_content):
            return ResolverResult(
                ok=False,
                artifact_version_id=artifact_version_id,
                code="CHAR_RANGE_INVALID",
                message=f"Char range {start_char}-{end_char} exceeds log length ({len(log_content)} chars)"
            )
        
        # Extract snippet
        snippet = log_content[start_char:end_char]
        
        return ResolverResult(
            ok=True,
            artifact_version_id=artifact_version_id,
            normalized_location=location,
            mime="text/plain",
            snippet=snippet,
            source={
                "artifact_id": version.artifact_id,
                "type": "log",
                "version": version.version
            }
        )


def create_resolver(storage, db) -> EvidenceResolver:
    """Factory function to create evidence resolver."""
    return EvidenceResolver(storage, db)
