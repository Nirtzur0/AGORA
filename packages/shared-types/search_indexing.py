"""
Shared search indexing helpers.

This logic is used by both synchronous browser uploads and worker-driven
ingestion so search indexing follows one canonical code path.
"""

from __future__ import annotations

from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - exercised where fitz is installed
    fitz = None


def extract_search_document(content: bytes, artifact_type: str) -> tuple[Optional[str], dict]:
    normalized_type = (artifact_type or "").lower()

    if normalized_type == "pdf":
        if fitz is None:
            return None, {"error": "fitz_unavailable"}
        doc = fitz.open(stream=content, filetype="pdf")
        page_text = [page.get_text().strip() for page in doc]
        return "\n\n".join(filter(None, page_text)), {"page_count": len(page_text)}

    if normalized_type in {"log", "draft", "code", "repo", "dataset", "config"}:
        return content.decode("utf-8", errors="replace"), {}

    return None, {}


def upsert_search_index(
    *,
    workspace_id: str,
    artifact_id: str,
    artifact_version_id: str,
    artifact_type: str,
    search_text: Optional[str],
    metadata: Optional[dict],
    db,
) -> None:
    if not search_text or not search_text.strip():
        return

    normalized_metadata = metadata or {}
    existing = db.execute(
        "SELECT id FROM search_index WHERE artifact_version_id = :artifact_version_id",
        {"artifact_version_id": str(artifact_version_id)},
    ).fetchone()

    if existing:
        db.execute(
            """
            UPDATE search_index
            SET content = :content,
                metadata = :metadata,
                indexed_at = NOW()
            WHERE artifact_version_id = :artifact_version_id
            """,
            {
                "artifact_version_id": str(artifact_version_id),
                "content": search_text,
                "metadata": normalized_metadata,
            },
        )
        return

    db.execute(
        """
        INSERT INTO search_index (
            workspace_id, artifact_id, artifact_version_id, artifact_type, content, metadata, indexed_at
        ) VALUES (
            :workspace_id, :artifact_id, :artifact_version_id, :artifact_type, :content, :metadata, NOW()
        )
        """,
        {
            "workspace_id": str(workspace_id),
            "artifact_id": str(artifact_id),
            "artifact_version_id": str(artifact_version_id),
            "artifact_type": artifact_type,
            "content": search_text,
            "metadata": normalized_metadata,
        },
    )

