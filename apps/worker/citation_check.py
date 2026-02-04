"""
Citation Check Activity (Component 13)

Per spec §4.11, §6.6, §5.8:
- Parse draft Markdown for [[claim:{claim_id}]] and [[cite:{artifact_version_id}|{location}]]
- Deterministic paragraph splitting (blank line separators)
- Coverage rule: every claim marker has ≥1 cite marker in same paragraph
- Validate IDs exist and belong to same workspace
- Resolves rule: every cite resolves via evidence resolver
- Materialize citations rows (claim × cite pairs in same paragraph)
- Write rule_checks rows: citation_coverage, citation_resolves
- Runs automatically on every draft version creation

This is a Temporal activity.
"""
import re
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from database import DBWrapper
from storage import create_storage_from_env
from evidence_resolver import resolve_evidence


@dataclass
class ClaimMarker:
    """Represents [[claim:{claim_id}]] marker."""
    claim_id: str
    paragraph_index: int


@dataclass
class CiteMarker:
    """Represents [[cite:{artifact_version_id}|{location}]] marker."""
    artifact_version_id: str
    location: str
    paragraph_index: int


@dataclass
class CitationCheckResult:
    """Result of citation check activity."""
    coverage_pass: bool
    coverage_failures: List[Dict[str, Any]]  # Claims without citations
    resolves_pass: bool
    resolves_failures: List[Dict[str, Any]]  # Citations that don't resolve
    citations_materialized: int


def parse_draft_markdown(markdown: str) -> tuple[List[ClaimMarker], List[CiteMarker], List[str]]:
    """
    Parse Markdown for claim and cite markers.
    
    Returns:
        - List of ClaimMarker (claim_id, paragraph_index)
        - List of CiteMarker (artifact_version_id, location, paragraph_index)
        - List of paragraphs (for deterministic splitting)
    
    Paragraphs are separated by one or more blank lines (deterministic).
    """
    # Split by blank lines (one or more consecutive newlines)
    paragraphs = re.split(r'\n\s*\n', markdown)
    
    claim_markers: List[ClaimMarker] = []
    cite_markers: List[CiteMarker] = []
    
    # Patterns per spec §5.8
    claim_pattern = re.compile(r'\[\[claim:([a-f0-9\-]+)\]\]')
    cite_pattern = re.compile(r'\[\[cite:([a-f0-9\-]+)\|([^\]]+)\]\]')
    
    for para_idx, paragraph in enumerate(paragraphs):
        # Find all claim markers in this paragraph
        for match in claim_pattern.finditer(paragraph):
            claim_id = match.group(1)
            claim_markers.append(ClaimMarker(
                claim_id=claim_id,
                paragraph_index=para_idx
            ))
        
        # Find all cite markers in this paragraph
        for match in cite_pattern.finditer(paragraph):
            artifact_version_id = match.group(1)
            location = match.group(2)
            cite_markers.append(CiteMarker(
                artifact_version_id=artifact_version_id,
                location=location,
                paragraph_index=para_idx
            ))
    
    return claim_markers, cite_markers, paragraphs


def validate_ids_in_workspace(
    db: DBWrapper,
    workspace_id: str,
    claim_ids: List[str],
    artifact_version_ids: List[str]
) -> tuple[List[str], List[str]]:
    """
    Validate that referenced IDs exist and belong to the workspace.
    
    Returns:
        - List of invalid claim_ids
        - List of invalid artifact_version_ids
    """
    invalid_claims = []
    invalid_versions = []
    
    # Check claims
    for claim_id in set(claim_ids):
        result = db.execute(
            """
            SELECT c.id FROM claims c
            WHERE c.id = :claim_id AND c.workspace_id = :workspace_id
            """,
            {"claim_id": claim_id, "workspace_id": workspace_id}
        ).fetchone()
        
        if not result:
            invalid_claims.append(claim_id)
    
    # Check artifact versions
    for version_id in set(artifact_version_ids):
        result = db.execute(
            """
            SELECT av.id FROM artifact_versions av
            JOIN artifacts a ON av.artifact_id = a.id
            WHERE av.id = :version_id AND a.workspace_id = :workspace_id
            """,
            {"version_id": version_id, "workspace_id": workspace_id}
        ).fetchone()
        
        if not result:
            invalid_versions.append(version_id)
    
    return invalid_claims, invalid_versions


def check_citation_coverage(
    claim_markers: List[ClaimMarker],
    cite_markers: List[CiteMarker]
) -> tuple[bool, List[Dict[str, Any]]]:
    """
    Check coverage rule: every claim marker has ≥1 cite marker in same paragraph.
    
    Returns:
        - pass: bool
        - failures: List of {claim_id, paragraph_index, reason}
    """
    failures = []
    
    # Group cite markers by paragraph
    cites_by_paragraph: Dict[int, List[CiteMarker]] = {}
    for cite in cite_markers:
        if cite.paragraph_index not in cites_by_paragraph:
            cites_by_paragraph[cite.paragraph_index] = []
        cites_by_paragraph[cite.paragraph_index].append(cite)
    
    # Check each claim has at least one citation in same paragraph
    for claim in claim_markers:
        para_cites = cites_by_paragraph.get(claim.paragraph_index, [])
        if not para_cites:
            failures.append({
                "claim_id": claim.claim_id,
                "paragraph_index": claim.paragraph_index,
                "reason": "no_citation_in_paragraph"
            })
    
    return len(failures) == 0, failures


def check_citation_resolves(
    db: DBWrapper,
    cite_markers: List[CiteMarker],
    workspace_id: str
) -> tuple[bool, List[Dict[str, Any]]]:
    """
    Check resolves rule: every cite resolves via evidence resolver.
    
    Returns:
        - pass: bool
        - failures: List of {artifact_version_id, location, reason, error_code}
    """
    failures = []
    storage = create_storage_from_env()
    
    for cite in cite_markers:
        try:
            # Get artifact version details
            version_row = db.execute(
                """
                SELECT av.storage_uri, av.content_hash, a.type, a.workspace_id
                FROM artifact_versions av
                JOIN artifacts a ON av.artifact_id = a.id
                WHERE av.id = :version_id
                """,
                {"version_id": cite.artifact_version_id}
            ).fetchone()
            
            if not version_row:
                failures.append({
                    "artifact_version_id": cite.artifact_version_id,
                    "location": cite.location,
                    "reason": "artifact_version_not_found",
                    "error_code": "VERSION_NOT_FOUND"
                })
                continue
            
            storage_uri, content_hash, artifact_type, art_ws_id = version_row
            
            # Verify workspace
            if art_ws_id != workspace_id:
                failures.append({
                    "artifact_version_id": cite.artifact_version_id,
                    "location": cite.location,
                    "reason": "workspace_mismatch",
                    "error_code": "WORKSPACE_MISMATCH"
                })
                continue
            
            # Try to resolve evidence
            resolution_result = resolve_evidence(
                artifact_version_id=cite.artifact_version_id,
                location=cite.location,
                storage=storage,
                db=db
            )
            
            if not resolution_result["success"]:
                failures.append({
                    "artifact_version_id": cite.artifact_version_id,
                    "location": cite.location,
                    "reason": resolution_result.get("error", "resolution_failed"),
                    "error_code": resolution_result.get("error_code", "RESOLUTION_FAILED")
                })
        
        except Exception as e:
            failures.append({
                "artifact_version_id": cite.artifact_version_id,
                "location": cite.location,
                "reason": str(e),
                "error_code": "RESOLUTION_ERROR"
            })
    
    return len(failures) == 0, failures


def materialize_citations(
    db: DBWrapper,
    workspace_id: str,
    draft_artifact_version_id: str,
    claim_markers: List[ClaimMarker],
    cite_markers: List[CiteMarker]
) -> int:
    """
    Materialize citations rows: for each claim × cite pair in same paragraph.
    
    Per spec: "recommend: for each claim in paragraph × each cite in paragraph
    create a row; deterministic and queryable"
    
    Returns: number of citations materialized
    """
    # Group by paragraph
    claims_by_para: Dict[int, List[ClaimMarker]] = {}
    cites_by_para: Dict[int, List[CiteMarker]] = {}
    
    for claim in claim_markers:
        if claim.paragraph_index not in claims_by_para:
            claims_by_para[claim.paragraph_index] = []
        claims_by_para[claim.paragraph_index].append(claim)
    
    for cite in cite_markers:
        if cite.paragraph_index not in cites_by_para:
            cites_by_para[cite.paragraph_index] = []
        cites_by_para[cite.paragraph_index].append(cite)
    
    count = 0
    
    # For each paragraph with both claims and cites, create cross product
    all_paragraphs = set(claims_by_para.keys()) | set(cites_by_para.keys())
    for para_idx in all_paragraphs:
        para_claims = claims_by_para.get(para_idx, [])
        para_cites = cites_by_para.get(para_idx, [])
        
        # Create citation for each claim × cite pair
        for claim in para_claims:
            for cite in para_cites:
                citation_id = str(uuid.uuid4())
                db.execute(
                    """
                    INSERT INTO citations (
                        id,
                        workspace_id,
                        draft_artifact_version_id,
                        claim_id,
                        source_artifact_version_id,
                        source_location
                    ) VALUES (
                        :id,
                        :workspace_id,
                        :draft_version_id,
                        :claim_id,
                        :source_version_id,
                        :source_location
                    )
                    """,
                    {
                        "id": citation_id,
                        "workspace_id": workspace_id,
                        "draft_version_id": draft_artifact_version_id,
                        "claim_id": claim.claim_id,
                        "source_version_id": cite.artifact_version_id,
                        "source_location": cite.location
                    }
                )
                count += 1
    
    db.commit()
    return count


def write_rule_check(
    db: DBWrapper,
    workspace_id: str,
    rule_name: str,
    target_type: str,
    target_id: str,
    status: str,
    details: Optional[Dict[str, Any]] = None
) -> str:
    """Write a rule_check record."""
    rule_check_id = str(uuid.uuid4())
    
    import json
    details_json = json.dumps(details) if details else None
    
    db.execute(
        """
        INSERT INTO rule_checks (
            id,
            workspace_id,
            rule_name,
            target_type,
            target_id,
            status,
            details
        ) VALUES (
            :id,
            :workspace_id,
            :rule_name,
            :target_type,
            :target_id,
            :status,
            :details
        )
        """,
        {
            "id": rule_check_id,
            "workspace_id": workspace_id,
            "rule_name": rule_name,
            "target_type": target_type,
            "target_id": target_id,
            "status": status,
            "details": details_json
        }
    )
    
    db.commit()
    return rule_check_id


def citation_check_activity(draft_artifact_version_id: str, db: DBWrapper) -> CitationCheckResult:
    """
    Main citation check activity.
    
    Per spec §6.6:
    - Runs automatically on every draft version creation
    - Checks citation_coverage and citation_resolves
    - Materializes citations rows
    - Writes rule_checks rows
    
    Args:
        draft_artifact_version_id: UUID of draft version to check
        db: Database wrapper
    
    Returns:
        CitationCheckResult with pass/fail status and details
    """
    storage = create_storage_from_env()
    
    # 1. Get draft version details
    version_row = db.execute(
        """
        SELECT av.storage_uri, av.artifact_id, a.workspace_id, a.type
        FROM artifact_versions av
        JOIN artifacts a ON av.artifact_id = a.id
        WHERE av.id = :version_id
        """,
        {"version_id": draft_artifact_version_id}
    ).fetchone()
    
    if not version_row:
        raise ValueError(f"Draft version {draft_artifact_version_id} not found")
    
    storage_uri, artifact_id, workspace_id, artifact_type = version_row
    
    if artifact_type != "draft":
        raise ValueError(f"Artifact {artifact_id} is not a draft (type={artifact_type})")
    
    # 2. Fetch Markdown content from storage
    # storage_uri should point directly to the draft markdown object
    markdown_bytes = storage.get_object(storage_uri).read()
    markdown = markdown_bytes.decode("utf-8")
    
    # 3. Parse Markdown for markers
    claim_markers, cite_markers, paragraphs = parse_draft_markdown(markdown)
    
    # 4. Validate IDs exist and belong to workspace
    claim_ids = [c.claim_id for c in claim_markers]
    artifact_version_ids = [c.artifact_version_id for c in cite_markers]
    
    invalid_claims, invalid_versions = validate_ids_in_workspace(
        db, workspace_id, claim_ids, artifact_version_ids
    )
    
    # If IDs are invalid, fail both checks
    if invalid_claims or invalid_versions:
        coverage_details = {
            "invalid_claim_ids": invalid_claims,
            "invalid_artifact_version_ids": invalid_versions,
            "reason": "referenced_ids_not_found"
        }
        
        write_rule_check(
            db, workspace_id, "citation_coverage", "draft_version",
            draft_artifact_version_id, "fail", coverage_details
        )
        
        write_rule_check(
            db, workspace_id, "citation_resolves", "draft_version",
            draft_artifact_version_id, "fail", coverage_details
        )
        
        return CitationCheckResult(
            coverage_pass=False,
            coverage_failures=[coverage_details],
            resolves_pass=False,
            resolves_failures=[coverage_details],
            citations_materialized=0
        )
    
    # 5. Check citation coverage
    coverage_pass, coverage_failures = check_citation_coverage(claim_markers, cite_markers)
    
    write_rule_check(
        db, workspace_id, "citation_coverage", "draft_version",
        draft_artifact_version_id,
        "pass" if coverage_pass else "fail",
        {
            "total_claims": len(claim_markers),
            "total_citations": len(cite_markers),
            "failures": coverage_failures
        }
    )
    
    # 6. Check citation resolves
    resolves_pass, resolves_failures = check_citation_resolves(db, cite_markers, workspace_id)
    
    write_rule_check(
        db, workspace_id, "citation_resolves", "draft_version",
        draft_artifact_version_id,
        "pass" if resolves_pass else "fail",
        {
            "total_citations": len(cite_markers),
            "failures": resolves_failures
        }
    )
    
    # 7. Materialize citations (only if both checks pass)
    citations_materialized = 0
    if coverage_pass and resolves_pass:
        citations_materialized = materialize_citations(
            db, workspace_id, draft_artifact_version_id, claim_markers, cite_markers
        )
    
    return CitationCheckResult(
        coverage_pass=coverage_pass,
        coverage_failures=coverage_failures,
        resolves_pass=resolves_pass,
        resolves_failures=resolves_failures,
        citations_materialized=citations_materialized
    )
