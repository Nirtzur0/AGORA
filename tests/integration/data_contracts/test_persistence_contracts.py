import pytest

from tests.helpers.assertions import assert_required_fields, assert_allowed_values


@pytest.mark.integration
@pytest.mark.postgres
def test_rule_checks__status_values__in_allowed_set(db_session):
    # This is a minimal persistence contract: rule_checks.status must be one of pass/fail/block.
    # If the table is empty, this still passes (contract is about allowed domain values).
    rows = db_session.execute("SELECT status FROM rule_checks").fetchall()
    statuses = [r[0] for r in rows]
    assert_allowed_values(statuses, {"pass", "fail", "block"}, context="rule_checks.status")


@pytest.mark.integration
@pytest.mark.postgres
def test_artifact_versions__required_columns_present(db_session):
    row = db_session.execute(
        "SELECT id, artifact_id, version, storage_uri, created_at FROM artifact_versions LIMIT 1"
    ).fetchone()
    # Table may be empty; we only assert shape when a row exists.
    if row is None:
        return
    assert_required_fields(
        {"id": row[0], "artifact_id": row[1], "version": row[2], "storage_uri": row[3], "created_at": row[4]},
        ["id", "artifact_id", "version", "storage_uri", "created_at"],
        context="artifact_versions.columns",
    )

