import pytest

from tests.helpers.assertions import assert_unique


@pytest.mark.unit
def test_ids__unique_constraint_helper():
    assert_unique(["a", "b", "c"], context="ids")

