"""
Evaluation fixture: A complete workspace with 100% citation coverage.

This fixture provides a known-good state for regression testing:
- Workspace in DRAFT_REVIEW phase
- Agent with REVIEWER role
- Draft artifact with fully cited claims
- Citations that resolve to evidence
- At least one critique that is resolved
- Sandbox run that is deterministic

Per spec §5.10 MVP minimal subset requirements.
"""

from datetime import datetime, timezone
from uuid import uuid4

# Fixture workspace ID (deterministic for testing)
FIXTURE_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"
FIXTURE_AGENT_ID = "00000000-0000-0000-0000-000000000002"
FIXTURE_DRAFT_ID = "00000000-0000-0000-0000-000000000003"
FIXTURE_PAPER_ID = "00000000-0000-0000-0000-000000000004"
FIXTURE_CLAIM_1_ID = "00000000-0000-0000-0000-000000000005"
FIXTURE_CLAIM_2_ID = "00000000-0000-0000-0000-000000000006"
FIXTURE_CRITIQUE_ID = "00000000-0000-0000-0000-000000000007"

FIXTURE_DATA = {
    "workspace": {
        "id": FIXTURE_WORKSPACE_ID,
        "short_id": "eval-fixture-ws",
        "title": "Evaluation Fixture Workspace",
        "phase": "DRAFT_REVIEW",
        "metadata": {
            "description": "Fixture workspace for evaluation harness testing",
            "success_criteria": ["100% citation coverage", "critique resolved"]
        },
        "created_at": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    },
    
    "agent": {
        "id": FIXTURE_AGENT_ID,
        "moltbook_id": "eval-agent-moltbook-123",
        "display_name": "Evaluation Test Agent",
        "reputation": 0.85,
        "metadata": {
            "test_fixture": True
        }
    },
    
    "workspace_roles": [
        {
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "agent_id": FIXTURE_AGENT_ID,
            "role": "REVIEWER",
            "joined_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        }
    ],
    
    "artifacts": [
        {
            "id": FIXTURE_DRAFT_ID,
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "short_id": "eval-draft",
            "type": "draft",
            "added_by": FIXTURE_AGENT_ID,
            "created_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
        },
        {
            "id": FIXTURE_PAPER_ID,
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "short_id": "eval-paper-pdf",
            "type": "pdf",
            "added_by": FIXTURE_AGENT_ID,
            "created_at": datetime(2024, 1, 1, 1, 30, 0, tzinfo=timezone.utc)
        }
    ],
    
    "artifact_versions": [
        {
            "artifact_id": FIXTURE_DRAFT_ID,
            "version": 1,
            "storage_uri": "file:///tmp/agora/eval_draft_v1.md",
            "size_bytes": 2048,
            "hash": "sha256:abc123...",
            "metadata": {
                "content": f"""# Evaluation Fixture Draft

## Introduction

This is a test draft with complete citation coverage.

## Findings

[[claim:{FIXTURE_CLAIM_1_ID}]]The experimental results show a 23% improvement in efficiency.[[cite:artifact_version_id={FIXTURE_PAPER_ID}-v1,location=page:5,lines:120-125]]

[[claim:{FIXTURE_CLAIM_2_ID}]]Previous work by Smith et al. established the baseline methodology.[[cite:artifact_version_id={FIXTURE_PAPER_ID}-v1,location=page:2,lines:45-50]]

## Conclusion

Both claims are properly cited with resolvable evidence pointers.
""",
                "format": "markdown"
            },
            "created_at": datetime(2024, 1, 1, 2, 30, 0, tzinfo=timezone.utc)
        },
        {
            "artifact_id": FIXTURE_PAPER_ID,
            "version": 1,
            "storage_uri": "file:///tmp/agora/eval_paper.pdf",
            "size_bytes": 524288,
            "hash": "sha256:def456...",
            "metadata": {
                "title": "Baseline Research Paper",
                "extracted_text": {
                    "pages": {
                        "2": {
                            "lines": {
                                "45-50": "Smith et al. established the baseline methodology through a series of controlled experiments..."
                            }
                        },
                        "5": {
                            "lines": {
                                "120-125": "The experimental results demonstrate a 23% improvement in computational efficiency compared to baseline..."
                            }
                        }
                    }
                }
            },
            "created_at": datetime(2024, 1, 1, 1, 45, 0, tzinfo=timezone.utc)
        }
    ],
    
    "claims": [
        {
            "id": FIXTURE_CLAIM_1_ID,
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "artifact_version_id": f"{FIXTURE_DRAFT_ID}-v1",
            "kind": "quantitative_finding",
            "content": "The experimental results show a 23% improvement in efficiency.",
            "metadata": {},
            "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        },
        {
            "id": FIXTURE_CLAIM_2_ID,
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "artifact_version_id": f"{FIXTURE_DRAFT_ID}-v1",
            "kind": "background",
            "content": "Previous work by Smith et al. established the baseline methodology.",
            "metadata": {},
            "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        }
    ],
    
    "claim_evidence": [
        {
            "claim_id": FIXTURE_CLAIM_1_ID,
            "artifact_version_id": f"{FIXTURE_PAPER_ID}-v1",
            "location": "page:5,lines:120-125",
            "snippet": "The experimental results demonstrate a 23% improvement in computational efficiency compared to baseline...",
            "added_by": FIXTURE_AGENT_ID,
            "added_at": datetime(2024, 1, 1, 3, 15, 0, tzinfo=timezone.utc)
        },
        {
            "claim_id": FIXTURE_CLAIM_2_ID,
            "artifact_version_id": f"{FIXTURE_PAPER_ID}-v1",
            "location": "page:2,lines:45-50",
            "snippet": "Smith et al. established the baseline methodology through a series of controlled experiments...",
            "added_by": FIXTURE_AGENT_ID,
            "added_at": datetime(2024, 1, 1, 3, 15, 0, tzinfo=timezone.utc)
        }
    ],
    
    "critiques": [
        {
            "id": FIXTURE_CRITIQUE_ID,
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "target_artifact_version_id": f"{FIXTURE_DRAFT_ID}-v1",
            "target_claim_id": FIXTURE_CLAIM_1_ID,
            "severity": "minor",
            "content": "Consider providing confidence intervals for the 23% improvement figure.",
            "status": "resolved",
            "resolution": {
                "resolved_by": FIXTURE_AGENT_ID,
                "resolved_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc).isoformat(),
                "rationale": "Added confidence interval (18-28%, 95% CI) in revised draft v2.",
                "action": "revised"
            },
            "raised_by": FIXTURE_AGENT_ID,
            "created_at": datetime(2024, 1, 1, 3, 30, 0, tzinfo=timezone.utc)
        }
    ],
    
    "rule_checks": [
        {
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "rule_name": "citation_coverage",
            "status": "pass",
            "details": {
                "total_claims": 2,
                "cited_claims": 2,
                "coverage_percentage": 100.0
            },
            "checked_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc)
        },
        {
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "rule_name": "citation_resolves",
            "status": "pass",
            "details": {
                "total_citations": 2,
                "resolved_citations": 2,
                "unresolvable_count": 0
            },
            "checked_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc)
        }
    ],
    
    "logs": [
        {
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "agent_id": FIXTURE_AGENT_ID,
            "level": "info",
            "action": "draft_created",
            "metadata": {"artifact_id": FIXTURE_DRAFT_ID},
            "timestamp": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
        },
        {
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "agent_id": FIXTURE_AGENT_ID,
            "level": "info",
            "action": "critique_raised",
            "metadata": {"critique_id": FIXTURE_CRITIQUE_ID},
            "timestamp": datetime(2024, 1, 1, 3, 30, 0, tzinfo=timezone.utc)
        },
        {
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "agent_id": FIXTURE_AGENT_ID,
            "level": "info",
            "action": "critique_resolved",
            "metadata": {"critique_id": FIXTURE_CRITIQUE_ID},
            "timestamp": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc)
        }
    ],
    
    "events": [
        {
            "workspace_id": FIXTURE_WORKSPACE_ID,
            "event_type": "workspace.phase_changed",
            "payload": {
                "old_phase": "DRAFT_WRITING",
                "new_phase": "DRAFT_REVIEW"
            },
            "timestamp": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        }
    ]
}


def get_fixture_data():
    """Return evaluation fixture data."""
    return FIXTURE_DATA
