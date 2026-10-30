"""Optional FastAPI surface. Importing this module requires FastAPI;
core gateway logic never depends on it, and API tests auto-skip without it.
"""

from __future__ import annotations

try:
    from fastapi import FastAPI, HTTPException, Request
except ImportError:  # pragma: no cover - exercised by skip tests
    FastAPI = None  # type: ignore

from .errors import ApprovalRequired, GatewayError
from .gateway import ToolGateway
from .models import AgentIdentity, ToolCallRequest


def create_app(gateway: ToolGateway):
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed; install requirements.txt")
    app = FastAPI(title="agent-tool-gateway")

    def _agent(body: dict) -> AgentIdentity:
        return AgentIdentity(
            agent_id=body.get("agent_id", "anonymous"),
            tenant_id=body.get("tenant_id", ""),
            scopes=frozenset(body.get("scopes", [])),
        )

    @app.get("/v1/tools")
    def list_tools():
        return [{"name": t.name, "version": t.version,
                 "description": t.description, "risk": t.risk.value,
                 "scopes": list(t.scopes)}
                for t in gateway.registry.list_tools()]

    @app.post("/v1/tools/{name}/invoke")
    async def invoke(name: str, request: Request):
        body = await request.json()
        try:
            result = gateway.execute(ToolCallRequest(
                agent=_agent(body), tool_name=name,
                arguments=body.get("arguments", {}),
                version=body.get("version", "latest"),
                idempotency_key=body.get("idempotency_key"),
                approval_id=body.get("approval_id"),
            ))
        except ApprovalRequired as exc:
            raise HTTPException(status_code=403, detail={
                "error": "approval_required", "approval_id": exc.approval_id})
        except GatewayError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return {"status": result.status, "output": result.output,
                "latency_ms": result.latency_ms, "cost_usd": result.cost_usd,
                "cached": result.cached}

    @app.post("/v1/approvals/{approval_id}/approve")
    async def approve(approval_id: str, request: Request):
        body = await request.json()
        try:
            approval = gateway.approve(approval_id, body.get("approver", "api"))
        except GatewayError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"approval_id": approval.approval_id, "status": approval.status}

    @app.get("/v1/audit/verify")
    def verify_audit():
        return {"valid": gateway.audit.verify(),
                "entries": len(gateway.audit.entries())}

    return app
