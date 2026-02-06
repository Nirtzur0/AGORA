import pytest

from tests.helpers.assertions import assert_allowed_values


@pytest.mark.unit
def test_gate_status__allowed_values():
    # GateStatus values observed in worker gates.
    statuses = ["PASS", "FAIL", "BLOCK"]
    assert_allowed_values(statuses, {"PASS", "FAIL", "BLOCK"}, context="gates.status")

