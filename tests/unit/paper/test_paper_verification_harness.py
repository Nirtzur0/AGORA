"""Deterministic verification harness for paper invariants."""

from __future__ import annotations

from collections import defaultdict

import citation_check
import phase_machine


def _coverage_ratio(claim_markers, cite_markers) -> float:
    if not claim_markers:
        return 1.0

    cites_by_paragraph = defaultdict(int)
    for cite in cite_markers:
        cites_by_paragraph[cite.paragraph_index] += 1

    covered_claims = sum(1 for claim in claim_markers if cites_by_paragraph[claim.paragraph_index] >= 1)
    return covered_claims / len(claim_markers)


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeMaterializeDB:
    def __init__(self):
        self._existing = set()
        self.inserted = []
        self.commit_count = 0

    def execute(self, query, params=None):
        if "SELECT id" in query and "FROM citations" in query:
            key = (
                params["workspace_id"],
                params["draft_version_id"],
                params["claim_id"],
                params["source_version_id"],
                params["source_location"],
            )
            if key in self._existing:
                return _FakeResult(("existing",))
            return _FakeResult(None)

        if "INSERT INTO citations" in query:
            key = (
                params["workspace_id"],
                params["draft_version_id"],
                params["claim_id"],
                params["source_version_id"],
                params["source_location"],
            )
            self._existing.add(key)
            self.inserted.append(key)
            return _FakeResult(None)

        return _FakeResult(None)

    def commit(self):
        self.commit_count += 1


# Limiting/sanity tests


def test_limiting_empty_markdown_produces_no_markers():
    claims, cites, paragraphs = citation_check.parse_draft_markdown("")

    assert claims == []
    assert cites == []
    assert paragraphs == [""]


def test_limiting_coverage_with_no_claims_passes_by_convention():
    coverage_pass, failures = citation_check.check_citation_coverage([], [])

    assert coverage_pass is True
    assert failures == []


def test_limiting_archived_is_terminal_phase():
    assert phase_machine.PhaseMachine.is_terminal_phase("ARCHIVED") is True
    assert phase_machine.PhaseMachine.is_terminal_phase("FINALIZED") is False


def test_limiting_materialization_second_run_is_idempotent():
    db = _FakeMaterializeDB()

    claims = [
        citation_check.ClaimMarker(
            claim_id="11111111-1111-1111-1111-111111111111", paragraph_index=0
        )
    ]
    cites = [
        citation_check.CiteMarker(
            artifact_version_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            location="pdf:p=1#char=0-10",
            paragraph_index=0,
        )
    ]

    first = citation_check.materialize_citations(
        db,
        workspace_id="aaaaaaaa-0000-0000-0000-000000000001",
        draft_artifact_version_id="bbbbbbbb-0000-0000-0000-000000000002",
        claim_markers=claims,
        cite_markers=cites,
    )
    second = citation_check.materialize_citations(
        db,
        workspace_id="aaaaaaaa-0000-0000-0000-000000000001",
        draft_artifact_version_id="bbbbbbbb-0000-0000-0000-000000000002",
        claim_markers=claims,
        cite_markers=cites,
    )

    assert first == 1
    assert second == 0


# Property/invariant tests


def test_property_citation_coverage_matches_indicator_equation():
    markdown = (
        "A [[claim:11111111-1111-1111-1111-111111111111]] "
        "[[cite:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa|pdf:p=1#char=0-10]]\n\n"
        "B [[claim:22222222-2222-2222-2222-222222222222]]\n\n"
        "C [[claim:33333333-3333-3333-3333-333333333333]] "
        "[[cite:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb|repo:path=README.md#L1-L5]]"
    )

    claims, cites, _ = citation_check.parse_draft_markdown(markdown)
    coverage_pass, _ = citation_check.check_citation_coverage(claims, cites)

    ratio = _coverage_ratio(claims, cites)

    assert ratio == 2 / 3
    assert coverage_pass is (ratio == 1.0)


def test_property_materialization_count_matches_cross_product_equation():
    db = _FakeMaterializeDB()

    claims = [
        citation_check.ClaimMarker(
            claim_id="11111111-1111-1111-1111-111111111111", paragraph_index=0
        ),
        citation_check.ClaimMarker(
            claim_id="22222222-2222-2222-2222-222222222222", paragraph_index=0
        ),
        citation_check.ClaimMarker(
            claim_id="33333333-3333-3333-3333-333333333333", paragraph_index=1
        ),
        citation_check.ClaimMarker(
            claim_id="44444444-4444-4444-4444-444444444444", paragraph_index=2
        ),
    ]

    cites = [
        citation_check.CiteMarker(
            artifact_version_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            location="pdf:p=1#char=0-10",
            paragraph_index=0,
        ),
        citation_check.CiteMarker(
            artifact_version_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            location="pdf:p=1#char=11-20",
            paragraph_index=0,
        ),
        citation_check.CiteMarker(
            artifact_version_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
            location="repo:path=README.md#L1-L5",
            paragraph_index=0,
        ),
        citation_check.CiteMarker(
            artifact_version_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
            location="log:char=0-5",
            paragraph_index=2,
        ),
    ]

    inserted_count = citation_check.materialize_citations(
        db,
        workspace_id="aaaaaaaa-0000-0000-0000-000000000001",
        draft_artifact_version_id="bbbbbbbb-0000-0000-0000-000000000002",
        claim_markers=claims,
        cite_markers=cites,
    )

    expected = (2 * 3) + (1 * 0) + (1 * 1)
    assert inserted_count == expected


def test_property_phase_validity_matches_adjacency_relation():
    expected_relation = {
        phase.value: {target.value for target in targets}
        for phase, targets in phase_machine.ALLOWED_TRANSITIONS.items()
    }

    all_phases = [phase.value for phase in phase_machine.WorkspacePhase]

    for current in all_phases:
        for nxt in all_phases:
            actual = phase_machine.PhaseMachine.is_valid_transition(current, nxt)
            expected = nxt in expected_relation[current]
            assert actual is expected


# Regression/golden tests


def test_golden_marker_extraction_snapshot():
    markdown = (
        "Intro [[claim:aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa]] "
        "[[cite:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa|pdf:p=1#char=0-15]]\n\n"
        "Methods [[claim:bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb]] "
        "[[claim:cccccccc-3333-3333-3333-cccccccccccc]] "
        "[[cite:bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb|repo:path=paper/main.tex#L1-L10]]"
    )

    claims, cites, _ = citation_check.parse_draft_markdown(markdown)

    claim_snapshot = [(c.claim_id, c.paragraph_index) for c in claims]
    cite_snapshot = [(c.artifact_version_id, c.location, c.paragraph_index) for c in cites]

    assert claim_snapshot == [
        ("aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa", 0),
        ("bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb", 1),
        ("cccccccc-3333-3333-3333-cccccccccccc", 1),
    ]
    assert cite_snapshot == [
        ("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "pdf:p=1#char=0-15", 0),
        (
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "repo:path=paper/main.tex#L1-L10",
            1,
        ),
    ]


def test_golden_allowed_transitions_snapshot():
    actual = {
        phase.value: sorted([target.value for target in targets])
        for phase, targets in phase_machine.ALLOWED_TRANSITIONS.items()
    }

    expected = {
        "INIT": ["LIT_REVIEW"],
        "LIT_REVIEW": ["CLAIM_VALIDATION"],
        "CLAIM_VALIDATION": ["HYPOTHESIS_PLANNING", "LIT_REVIEW"],
        "HYPOTHESIS_PLANNING": ["EXPERIMENTATION"],
        "EXPERIMENTATION": ["SYNTHESIS"],
        "SYNTHESIS": ["INTERNAL_REVIEW"],
        "INTERNAL_REVIEW": ["EXPERIMENTATION", "FINALIZED"],
        "FINALIZED": ["ARCHIVED"],
        "ARCHIVED": [],
    }

    assert actual == expected
