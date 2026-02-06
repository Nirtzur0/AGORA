from __future__ import annotations

from typing import Any, Mapping


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def json_of(response: Any) -> Any:
    # requests.Response and starlette TestResponse both expose .json()
    return response.json()


def assert_status(response: Any, expected_status: int, *, context: str = "") -> None:
    actual = getattr(response, "status_code", None)
    if actual != expected_status:
        ctx = f" context={context!r}" if context else ""
        body_preview = ""
        try:
            body_preview = f" body={response.text[:800]!r}"
        except Exception:
            try:
                body_preview = f" json={json_of(response)!r}"
            except Exception:
                body_preview = ""
        raise AssertionError(f"Unexpected status{ctx}: expected={expected_status} actual={actual}.{body_preview}")


def assert_error_code(response_json: Mapping[str, Any], expected: str, *, context: str = "") -> None:
    # Many endpoints use FastAPI's {"detail": {...}} shape; tolerate both.
    payload = response_json.get("detail") if "detail" in response_json else response_json
    code = None
    if isinstance(payload, dict):
        code = payload.get("error") or payload.get("code")
    ctx = f" context={context!r}" if context else ""
    if code != expected:
        raise AssertionError(f"Unexpected error code{ctx}: expected={expected!r} actual={code!r} payload={response_json!r}")

