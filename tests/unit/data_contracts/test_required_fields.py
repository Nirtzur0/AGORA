import pytest

from tests.helpers.assertions import assert_required_fields, assert_non_null_fields


@pytest.mark.unit
def test_resolver_result__success__has_required_fields():
    sample = {
        "ok": True,
        "artifact_version_id": "00000000-0000-0000-0000-000000000000",
        "normalized_location": "pdf:p=1#char=0-10",
        "mime": "text/plain",
        "snippet": "hello",
        "source": {"type": "pdf", "version": 1},
    }
    assert_required_fields(sample, ["ok", "artifact_version_id", "normalized_location", "mime", "snippet", "source"], context="resolver.success")
    assert_non_null_fields(sample, ["artifact_version_id", "normalized_location", "mime", "snippet", "source"], context="resolver.success")


@pytest.mark.unit
def test_resolver_result__error__has_required_fields():
    sample = {"ok": False, "code": "INVALID_LOCATION_FORMAT", "message": "..."}
    assert_required_fields(sample, ["ok", "code", "message"], context="resolver.error")
    assert_non_null_fields(sample, ["code", "message"], context="resolver.error")

