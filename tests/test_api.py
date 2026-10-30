import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")

from fastapi.testclient import TestClient

from agent_tool_gateway.api import create_app


@pytest.fixture()
def client(gateway):
    return TestClient(create_app(gateway))


def test_list_tools(client):
    names = {t["name"] for t in client.get("/v1/tools").json()}
    assert {"calculator", "echo", "data_export"} <= names


def test_invoke_and_approval_required(client):
    body = {"agent_id": "agent-1", "tenant_id": "tenant-a",
            "scopes": ["tools:calculator"], "arguments": {"op": "add", "a": 1, "b": 2}}
    resp = client.post("/v1/tools/calculator/invoke", json=body)
    assert resp.status_code == 200 and resp.json()["output"] == {"result": 3}
    denied = client.post("/v1/tools/data_export/invoke", json={
        "agent_id": "agent-1", "tenant_id": "tenant-a",
        "scopes": ["tools:export"],
        "arguments": {"row_limit": 1, "format": "json"}})
    assert denied.status_code == 403
    assert denied.json()["detail"]["error"] == "approval_required"
