import pytest

from tests.helpers.assertions import assert_required_fields


@pytest.mark.integration
def test_health_endpoint__shape(core_api_app):
    # Use in-process client via fixture from tests/conftest.py.
    from fastapi.testclient import TestClient

    client = TestClient(core_api_app)
    r = client.get("/health")
    assert r.status_code == 200
    payload = r.json()
    assert_required_fields(payload, ["status", "service", "version"], context="GET /health")

