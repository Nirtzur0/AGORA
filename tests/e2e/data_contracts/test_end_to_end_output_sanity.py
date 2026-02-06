import pytest

from tests.helpers.assertions import assert_allowed_values


@pytest.mark.e2e
@pytest.mark.slow
def test_sanity__rule_checks_statuses__valid_domain(db_session):
    # E2E sanity: if rule_checks exist (from any workflow), ensure status domain is respected.
    rows = db_session.execute("SELECT status FROM rule_checks").fetchall()
    statuses = [r[0] for r in rows]
    assert_allowed_values(statuses, {"pass", "fail", "block"}, context="e2e.rule_checks.status")

