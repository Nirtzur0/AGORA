"""
Integration tests for search indexing and retrieval.
"""

from tests.integration.core_api.test_workspaces import agent_tokens, created_workspace  # noqa: F401


def test_search__uploaded_log_version__returns_matching_hit(test_client, created_workspace, agent_tokens):
    unique_token = "search-regression-token-42b7f4"

    artifact_response = test_client.post(
        f"/workspaces/{created_workspace}/artifacts",
        json={"type": "log", "metadata": {"title": "Searchable log"}},
        headers=agent_tokens["maintainer"]["headers"],
    )
    assert artifact_response.status_code == 201, artifact_response.text
    artifact = artifact_response.json()

    version_response = test_client.post(
        f"/artifacts/{artifact['id']}/versions",
        headers=agent_tokens["maintainer"]["headers"],
        files={"file": ("search.log", f"alpha\n{unique_token}\nomega\n".encode("utf-8"), "text/plain")},
    )
    assert version_response.status_code == 201, version_response.text
    version = version_response.json()

    search_response = test_client.get(
        f"/search?workspace_id={created_workspace}&query={unique_token}",
        headers=agent_tokens["maintainer"]["headers"],
    )
    assert search_response.status_code == 200, search_response.text

    payload = search_response.json()
    assert payload["total_hits"] >= 1
    assert any(hit["artifact_version_id"] == version["id"] for hit in payload["hits"])
