import uuid


def test_claim_create__valid_request__persists_claim_with_defaults(db_session, workspace_with_agent):
    """Test basic claim creation."""
    from claim_routes import CreateClaimRequest, create_claim
    from database import Claim

    workspace, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}

    request = CreateClaimRequest(
        kind="fact",
        text="Machine learning models can generalize from training data.",
        confidence="high",
    )

    result = create_claim(
        workspace_id=uuid.UUID(str(workspace.id)),
        request=request,
        current_agent=mock_agent,
        db=db_session,
    )

    assert result.workspace_id == str(workspace.id)
    assert result.kind == "fact"
    assert result.text == request.text
    assert result.confidence == "high"
    assert result.is_key is False
    assert result.status == "active"
    assert len(result.evidence) == 0

    claim = db_session.query(Claim).filter_by(id=result.id).first()
    assert claim is not None
    assert claim.text == request.text


def test_claim_create__missing_kind__defaults_to_fact(db_session, workspace_with_agent):
    """Claim kind defaults to fact."""
    from claim_routes import CreateClaimRequest, create_claim

    workspace, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}

    result = create_claim(
        workspace_id=uuid.UUID(str(workspace.id)),
        request=CreateClaimRequest(text="Test claim without kind"),
        current_agent=mock_agent,
        db=db_session,
    )

    assert result.kind == "fact"


def test_claim_create__is_key_set_by_agent__rejected_or_ignored(db_session, workspace_with_agent):
    """is_key remains system-owned for agent-created claims."""
    from claim_routes import CreateClaimRequest, create_claim

    workspace, agent = workspace_with_agent
    mock_agent = {"agent_id": agent.id}

    result = create_claim(
        workspace_id=uuid.UUID(str(workspace.id)),
        request=CreateClaimRequest(kind="fact", text="Test claim"),
        current_agent=mock_agent,
        db=db_session,
    )

    assert result.is_key is False
