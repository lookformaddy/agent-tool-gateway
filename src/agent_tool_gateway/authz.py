"""Fail-closed authorization.

Rules, in order:
1. Unknown tenant -> deny. Unknown tool -> deny (handled by the registry).
2. Every scope the tool requires must be held by the agent AND allowed
   for the tenant. Anything missing -> deny.
3. HIGH/CRITICAL tools additionally require a live approval (checked by
   the gateway, not here, so the approval lifecycle stays in one place).

There is no default-allow path: an empty scope set authorizes nothing
beyond tools that declare no scopes.
"""

from __future__ import annotations

from .errors import Unauthorized
from .models import AgentIdentity, TenantPolicy, ToolDefinition


class Authorizer:
    def __init__(self, tenant_policies: dict[str, TenantPolicy]) -> None:
        self._tenants = tenant_policies

    def authorize(self, agent: AgentIdentity, tool: ToolDefinition) -> None:
        policy = self._tenants.get(agent.tenant_id)
        if policy is None:
            raise Unauthorized(f"unknown tenant: {agent.tenant_id}")
        missing_agent = [s for s in tool.scopes if s not in agent.scopes]
        if missing_agent:
            raise Unauthorized(
                f"agent {agent.agent_id} lacks scopes: {', '.join(missing_agent)}"
            )
        missing_tenant = [s for s in tool.scopes if s not in policy.allowed_scopes]
        if missing_tenant:
            raise Unauthorized(
                f"tenant {agent.tenant_id} disallows scopes: {', '.join(missing_tenant)}"
            )
