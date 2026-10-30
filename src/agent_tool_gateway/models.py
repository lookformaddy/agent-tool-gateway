"""Core data models. Pure dataclasses; no I/O, no network, no framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def requires_approval(self) -> bool:
        return self in (RiskTier.HIGH, RiskTier.CRITICAL)


@dataclass(frozen=True)
class ToolDefinition:
    """A versioned tool contract registered in the gateway."""

    name: str
    version: str
    description: str
    input_schema: dict
    output_schema: dict
    scopes: tuple[str, ...] = ()
    risk: RiskTier = RiskTier.LOW
    rate_limit_per_minute: int = 60
    timeout_seconds: float = 5.0
    cost_usd_per_call: float = 0.0
    deprecated: bool = False

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"


@dataclass(frozen=True)
class AgentIdentity:
    """Who is calling: an agent acting on behalf of a tenant."""

    agent_id: str
    tenant_id: str
    scopes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class TenantPolicy:
    """Per-tenant allow-list. Unknown tenants are denied (fail closed)."""

    tenant_id: str
    allowed_scopes: frozenset[str] = frozenset()


@dataclass
class ToolCallRequest:
    agent: AgentIdentity
    tool_name: str
    arguments: dict
    version: str = "latest"
    idempotency_key: str | None = None
    approval_id: str | None = None


@dataclass
class ToolCallResult:
    status: str  # "ok"
    tool_name: str
    version: str
    output: dict
    latency_ms: float
    cost_usd: float
    cached: bool = False
    idempotency_key: str | None = None


@dataclass
class Approval:
    approval_id: str
    agent_id: str
    tenant_id: str
    tool_name: str
    version: str
    arguments_hash: str
    status: str = "pending"  # pending | approved | rejected | consumed
    approver: str | None = None


@dataclass
class AuditEntry:
    seq: int
    timestamp: str
    prev_hash: str
    entry_hash: str
    agent_id: str
    tenant_id: str
    tool_name: str
    version: str
    decision: str  # ok | denied | error
    reason: str
    latency_ms: float
    cost_usd: float
    idempotency_key: str | None = None
    arguments_hash: str = ""
