"""
PDF Ingestion Activity for AGORA Temporal Worker.

Implements PDF parsing and storage per spec §6.1:
- Store PDF binary in MinIO
- Parse text with PyMuPDF (fitz)
- Store per-page extracted text for evidence resolution
- Create artifact_versions row
- Write logs + activity_runs
- Fail if no text extracted (no OCR fallback)

Evidence pointer format: pdf:p={page}#char={start}-{end}
"""
import io
import json
from typing import Dict, Any, Optional
from uuid import uuid4
from datetime import datetime
import logging

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


class PDFIngestionError(Exception):
    """Base exception for PDF ingestion failures."""
    def __init__(self, message="PDF ingestion failed"):
        self.message = message
        super().__init__(self.message)


class NoPDFTextError(PDFIngestionError):
    """Raised when PDF contains no extractable text."""
    def __init__(self, message="No text content extracted from PDF"):
        super().__init__(message)


class PDFIngestActivity:
    """
    Temporal activity for PDF ingestion.
    
    Handles:
    - PDF binary storage
    - Text extraction with PyMuPDF
    - Per-page text storage for evidence resolution
    - Artifact version creation
    """
    
    def __init__(self, storage, db):
        """
        Initialize PDF ingestion activity.
        
        Args:
            storage: Storage instance for MinIO operations
            db: Database connection for artifact_versions/logs
        """
        self.storage = storage
        self.db = db
        
        if fitz is None:
            raise RuntimeError(
                "PyMuPDF (fitz) is not installed. "
                "Install with: pip install PyMuPDF"
            )
    
    def ingest_pdf(
        self,
        artifact_id: str,
        workspace_id: str,
        pdf_bytes: bytes,
        created_by: str,
        activity_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingest PDF: store binary + extract text + create artifact_version.
        
        Args:
            artifact_id: Artifact UUID
            workspace_id: Workspace UUID
            pdf_bytes: PDF binary content
            created_by: Agent UUID who initiated ingestion
            activity_run_id: Optional activity run ID for logging
            
        Returns:
            Dict with artifact_version_id, version, page_count, storage_uris
            
        Raises:
            NoPDFTextError: If PDF contains no extractable text
            PDFIngestionError: On other ingestion failures
        """
        logger.info(f"Starting PDF ingestion for artifact {artifact_id}")
        
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
            
            # Parse PDF to extract text
            extracted_pages = self._extract_pdf_text(pdf_bytes)
            
            if not extracted_pages:
                error_msg = "PDF contains no extractable text. OCR not implemented."
                logger.error(error_msg)
                self._write_log(
                    workspace_id, created_by, "pdf.ingestion_failed",
                    {"artifact_id": artifact_id, "error": error_msg}
                )
                raise NoPDFTextError(error_msg)
            
            # Store PDF binary
            binary_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{next_version}/document.pdf"
            self.storage.put_object(binary_uri, pdf_bytes)
            logger.info(f"Stored PDF binary at {binary_uri}")
            
            # Store per-page extracted text
            text_storage_uris = {}
            for page_num, page_text in extracted_pages.items():
                page_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{next_version}/pages/page_{page_num}.txt"
                self.storage.put_object(page_uri, page_text.encode('utf-8'))
                text_storage_uris[page_num] = page_uri
            
            logger.info(f"Stored {len(extracted_pages)} pages of extracted text")
            
            # Store page metadata (for quick lookup)
            metadata = {
                "page_count": len(extracted_pages),
                "text_storage_uris": text_storage_uris,
                "binary_uri": binary_uri
            }
            metadata_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{next_version}/metadata.json"
            self.storage.put_object(metadata_uri, json.dumps(metadata).encode('utf-8'))
            
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
                    "storage_uri": binary_uri,  # Primary storage URI points to binary
                    "content_hash": self._calculate_hash(pdf_bytes),
                    "created_by": created_by,
                    "created_at": datetime.utcnow()
                }
            )
            
            # Write success log
            self._write_log(
                workspace_id, created_by, "pdf.ingestion_completed",
                {
                    "artifact_id": artifact_id,
                    "artifact_version_id": str(version_id),
                    "version": next_version,
                    "page_count": len(extracted_pages),
                    "size_bytes": len(pdf_bytes)
                }
            )
            
            self.db.commit()
            
            logger.info(f"PDF ingestion completed: version_id={version_id}, pages={len(extracted_pages)}")
            
            return {
                "artifact_version_id": str(version_id),
                "version": next_version,
                "page_count": len(extracted_pages),
                "binary_uri": binary_uri,
                "metadata_uri": metadata_uri,
                "text_storage_uris": text_storage_uris
            }
            
        except NoPDFTextError:
            raise
        except Exception as e:
            error_msg = f"PDF ingestion failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self._write_log(
                workspace_id, created_by, "pdf.ingestion_failed",
                {"artifact_id": artifact_id, "error": error_msg}
            )
            raise PDFIngestionError(error_msg) from e
    
    def _extract_pdf_text(self, pdf_bytes: bytes) -> Dict[int, str]:
        """
        Extract text from PDF using PyMuPDF.
        
        Args:
            pdf_bytes: PDF binary content
            
        Returns:
            Dict mapping page number (1-based) to extracted text
            
        Raises:
            PDFIngestionError: If PDF cannot be opened or parsed
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            extracted_pages = {}
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # Only include pages with actual text
                if text.strip():
                    # Use 1-based page numbering (per spec)
                    extracted_pages[page_num + 1] = text
            
            doc.close()
            return extracted_pages
            
        except Exception as e:
            raise PDFIngestionError(f"Failed to parse PDF: {str(e)}") from e
    
    def resolve_pdf_evidence(
        self,
        artifact_version_id: str,
        location: str
    ) -> str:
        """
        Resolve evidence pointer to actual text substring.
        
        Format: pdf:p={page}#char={start}-{end}
        
        Args:
            artifact_version_id: Artifact version UUID
            location: Evidence location (e.g., "pdf:p=10#char=1200-1400")
            
        Returns:
            Extracted text substring
            
        Raises:
            ValueError: If location format is invalid or page/char range is out of bounds
        """
        # Parse location format
        if not location.startswith("pdf:p="):
            raise ValueError(f"Invalid PDF location format: {location}")
        
        try:
            # Extract page and char range
            parts = location[6:].split("#char=")
            page_num = int(parts[0])
            char_range = parts[1].split("-")
            start_char = int(char_range[0])
            end_char = int(char_range[1])
        except (IndexError, ValueError) as e:
            raise ValueError(f"Invalid PDF location format: {location}") from e
        
        # Get artifact version metadata
        result = self.db.execute(
            """
            SELECT artifact_id, version, storage_uri FROM artifact_versions
            WHERE id = :version_id
            """,
            {"version_id": artifact_version_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Artifact version not found: {artifact_version_id}")
        
        artifact_id, version, _ = row
        
        # Reconstruct page text URI
        # Get workspace_id from artifact
        result = self.db.execute(
            "SELECT workspace_id FROM artifacts WHERE id = :artifact_id",
            {"artifact_id": artifact_id}
        )
        workspace_row = result.fetchone()
        if not workspace_row:
            raise ValueError(f"Artifact not found: {artifact_id}")
        
        workspace_id = workspace_row[0]
        page_uri = f"s3://agora/{workspace_id}/artifacts/{artifact_id}/v{version}/pages/page_{page_num}.txt"
        
        # Retrieve page text
        try:
            page_stream = self.storage.get_object(page_uri)
            page_text = page_stream.read().decode('utf-8')
        except Exception as e:
            raise FileNotFoundError(f"Page {page_num} not found or cannot be read") from e
        
        # Extract character range
        if start_char < 0 or end_char > len(page_text) or start_char >= end_char:
            raise ValueError(
                f"Character range {start_char}-{end_char} is invalid for page {page_num} "
                f"(page has {len(page_text)} characters)"
            )
        
        return page_text[start_char:end_char]
    
    def _write_log(self, workspace_id: str, agent_id: str, action: str, payload: Dict):
        """Write log entry to database."""
        try:
            log_id = uuid4()
            self.db.execute(
                """
                INSERT INTO logs (id, workspace_id, agent_id, action, payload, created_at)
                VALUES (:id, :workspace_id, :agent_id, :action, :payload, :created_at)
                """,
                {
                    "id": str(log_id),
                    "workspace_id": workspace_id,
                    "agent_id": agent_id,
                    "action": action,
                    "payload": payload,
                    "created_at": datetime.utcnow()
                }
            )
        except Exception as e:
            logger.error(f"Failed to write log: {e}")
    
    def _calculate_hash(self, data: bytes) -> str:
        """Calculate SHA256 hash of data."""
        import hashlib
        return hashlib.sha256(data).hexdigest()
