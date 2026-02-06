import pytest

from tests.helpers.assertions import assert_missing_rate


@pytest.mark.unit
def test_missingness__below_threshold():
    rows = [
        {"field": "x"},
        {"field": "y"},
        {"field": None},
        {"field": "z"},
    ]
    # 25% missing; allow up to 0.30 for this synthetic example.
    assert_missing_rate(rows, "field", 0.30, context="synthetic")

