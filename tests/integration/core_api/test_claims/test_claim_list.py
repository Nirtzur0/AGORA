import uuid


def test_claims_list__with_evidence__includes_evidence(db_session, pdf_artifact_with_evidence):
    """Listing claims includes attached evidence rows."""
    from claim_routes import list_claims
    from database import Claim, ClaimEvidence

    data = pdf_artifact_with_evidence
    workspace = data["workspace"]
    agent = data["agent"]
    version = data["version"]

    claim1 = Claim(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        kind="fact",
        text="First claim",
        status="active",
        created_by=agent.id,
    )
    claim2 = Claim(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        kind="hypothesis",
        text="Second claim",
        confidence="medium",
        status="active",
        created_by=agent.id,
    )
    db_session.add_all([claim1, claim2])

    evidence1 = ClaimEvidence(
        id=str(uuid.uuid4()),
        claim_id=claim1.id,
        artifact_version_id=str(version.id),
        location="pdf:p=1#char=0-10",
    )
    evidence2 = ClaimEvidence(
        id=str(uuid.uuid4()),
        claim_id=claim1.id,
        artifact_version_id=str(version.id),
        location="pdf:p=1#char=20-30",
    )
    db_session.add_all([evidence1, evidence2])
    db_session.commit()

    result = list_claims(
        workspace_id=uuid.UUID(str(workspace.id)),
        current_agent={"agent_id": agent.id},
        db=db_session,
    )

    assert result["workspace_id"] == str(workspace.id)
    assert result["total"] == 2
    assert len(result["claims"]) == 2

    claim1_result = next(claim for claim in result["claims"] if claim["id"] == str(claim1.id))
    assert len(claim1_result["evidence"]) == 2

    claim2_result = next(claim for claim in result["claims"] if claim["id"] == str(claim2.id))
    assert len(claim2_result["evidence"]) == 0
