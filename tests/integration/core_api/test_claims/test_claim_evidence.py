import uuid

import pytest


def test_claim_evidence_add__resolvable_location__persists_evidence(db_session, pdf_artifact_with_evidence):
    """Adding evidence with a valid location persists evidence row."""
    from claim_routes import AddEvidenceRequest, add_evidence_to_claim
    from database import Claim, ClaimEvidence
    from storage import create_storage_from_env

    data = pdf_artifact_with_evidence
    workspace = data["workspace"]
    agent = data["agent"]
    version = data["version"]
    page1_text = data["page1_text"]

    claim = Claim(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        kind="fact",
        text="Test claim",
        status="active",
        created_by=agent.id,
    )
    db_session.add(claim)
    db_session.commit()

    search = "evidence"
    start_idx = page1_text.find(search)
    end_idx = start_idx + len(search)

    result = add_evidence_to_claim(
        claim_id=uuid.UUID(str(claim.id)),
        request=AddEvidenceRequest(
            artifact_version_id=str(version.id),
            location=f"pdf:p=1#char={start_idx}-{end_idx}",
        ),
        current_agent={"agent_id": agent.id},
        db=db_session,
        storage=create_storage_from_env(),
    )

    assert result["claim_id"] == str(claim.id)
    assert result["artifact_version_id"] == str(version.id)
    assert "resolved_snippet" in result
    assert search in result["resolved_snippet"]

    evidence = db_session.query(ClaimEvidence).filter_by(claim_id=claim.id).first()
    assert evidence is not None
    assert str(evidence.artifact_version_id) == str(version.id)


def test_claim_evidence_add__unresolvable_location__returns_400(db_session, pdf_artifact_with_evidence):
    """
    EXIT TEST 1: Evidence add fails if location doesn't resolve.

    Success criteria:
    - Returns 422 status
    - Returns resolver error codes
    - Error message is actionable
    """
    from claim_routes import AddEvidenceRequest, add_evidence_to_claim
    from database import Claim
    from fastapi import HTTPException
    from storage import create_storage_from_env

    data = pdf_artifact_with_evidence
    workspace = data["workspace"]
    agent = data["agent"]
    version = data["version"]

    claim = Claim(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        kind="fact",
        text="Test claim",
        status="active",
        created_by=agent.id,
    )
    db_session.add(claim)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_page:
        add_evidence_to_claim(
            claim_id=uuid.UUID(str(claim.id)),
            request=AddEvidenceRequest(
                artifact_version_id=str(version.id),
                location="pdf:p=999#char=0-10",
            ),
            current_agent={"agent_id": agent.id},
            db=db_session,
            storage=create_storage_from_env(),
        )
    assert exc_page.value.status_code == 422
    assert exc_page.value.detail["ok"] is False
    assert exc_page.value.detail["code"] == "PAGE_OUT_OF_RANGE"

    with pytest.raises(HTTPException) as exc_range:
        add_evidence_to_claim(
            claim_id=uuid.UUID(str(claim.id)),
            request=AddEvidenceRequest(
                artifact_version_id=str(version.id),
                location="pdf:p=1#char=100-50",
            ),
            current_agent={"agent_id": agent.id},
            db=db_session,
            storage=create_storage_from_env(),
        )
    assert exc_range.value.status_code == 422
    assert exc_range.value.detail["code"] == "CHAR_RANGE_INVALID"

    with pytest.raises(HTTPException) as exc_oob:
        add_evidence_to_claim(
            claim_id=uuid.UUID(str(claim.id)),
            request=AddEvidenceRequest(
                artifact_version_id=str(version.id),
                location="pdf:p=1#char=0-999999",
            ),
            current_agent={"agent_id": agent.id},
            db=db_session,
            storage=create_storage_from_env(),
        )
    assert exc_oob.value.status_code == 422
    assert exc_oob.value.detail["code"] == "CHAR_RANGE_INVALID"


def test_claim_evidence_add__version_from_other_workspace__returns_400(
    db_session,
    pdf_artifact_with_evidence,
    other_workspace_artifact,
):
    """
    EXIT TEST 2: Evidence add fails if version is from another workspace.

    Success criteria:
    - Returns 422 status
    - Returns WORKSPACE_MISMATCH error code
    - Prevents cross-workspace evidence contamination
    """
    from claim_routes import AddEvidenceRequest, add_evidence_to_claim
    from database import Claim
    from fastapi import HTTPException
    from storage import create_storage_from_env

    data = pdf_artifact_with_evidence
    workspace = data["workspace"]
    agent = data["agent"]
    other_version = other_workspace_artifact["version"]

    claim = Claim(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        kind="fact",
        text="Test claim",
        status="active",
        created_by=agent.id,
    )
    db_session.add(claim)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        add_evidence_to_claim(
            claim_id=uuid.UUID(str(claim.id)),
            request=AddEvidenceRequest(
                artifact_version_id=str(other_version.id),
                location="pdf:p=1#char=0-10",
            ),
            current_agent={"agent_id": agent.id},
            db=db_session,
            storage=create_storage_from_env(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["ok"] is False
    assert exc_info.value.detail["code"] == "WORKSPACE_MISMATCH"
    assert "not in the same workspace" in exc_info.value.detail["message"]
