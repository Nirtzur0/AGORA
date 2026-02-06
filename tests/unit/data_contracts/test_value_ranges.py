import pytest

from tests.helpers.assertions import assert_in_range


@pytest.mark.unit
def test_probability_like_values__in_0_1_range():
    assert_in_range([0, 0.5, 1.0], min=0.0, max=1.0, context="probabilities")

