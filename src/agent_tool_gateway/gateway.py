"""The gateway: registry + authorization + approval + rate limit + audit.

Execution pipeline (fail-closed at every step):
  resolve -> authorize -> validate args -> idempotency -> approval gate
  -> rate limit -> execute with timeout -> validate output -> audit/account
Every outcome, including denials, is appended to the hash-chained audit log.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .accounting import CostLedger
from .audit import AuditLog, hash_arguments
from .authz import Authorizer
from .errors import (
    ApprovalNotFound,
    ApprovalRequired,
    IdempotencyConflict,
    RateLimited,
    ToolExecutionError,
    ToolNotFound,
    ToolTimeout,
    Unauthorized,
    ValidationError,
)
from .models import (
    AgentIdentity,
    Approval,
    TenantPolicy,
    ToolCallRequest,
    ToolCallResult,
)
from .rate_limit import RateLimiter
from .registry import ToolRegistry
from .schema import validate


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        executors: dict,
        tenant_policies: dict[str, TenantPolicy],
    ) -> None:
        self.registry = registry
        self.executors = executors
        self.authorizer = Authorizer(tenant_policies)
        self.rate_limiter = RateLimiter()
        self.audit = AuditLog()
        self.ledger = CostLedger()
        self._approvals: dict[str, Approval] = {}
        self._idempotent: dict[str, tuple[str, ToolCallResult]] = {}

    # -- approvals ---------------------------------------------------------
    def approve(self, approval_id: str, approver: str) -> Approval:
        approval = self._approvals.get(approval_id)
        if approval is None or approval.status != "pending":
            raise ApprovalNotFound(f"no pending approval: {approval_id}")
        approval.status = "approved"
        approval.approver = approver
        return approval

    def reject(self, approval_id: str, approver: str) -> Approval:
        approval = self._approvals.get(approval_id)
        if approval is None or approval.status != "pending":
            raise ApprovalNotFound(f"no pending approval: {approval_id}")
        approval.status = "rejected"
        approval.approver = approver
        return approval

    def pending_approvals(self) -> list[Approval]:
        return [a for a in self._approvals.values() if a.status == "pending"]

    # -- execution ---------------------------------------------------------
    def execute(self, request: ToolCallRequest) -> ToolCallResult:
        agent = request.agent
        started = time.monotonic()
        tool = None
        try:
            tool = self.registry.get(request.tool_name, request.version)
            self.authorizer.authorize(agent, tool)
            errors = validate(request.arguments, tool.input_schema)
            if errors:
                raise ValidationError("; ".join(errors))
            args_hash = hash_arguments(request.arguments)
            if request.idempotency_key:
                prior = self._idempotent.get(request.idempotency_key)
                if prior is not None:
                    prior_hash, prior_result = prior
                    if prior_hash != args_hash:
                        raise IdempotencyConflict(
                            f"idempotency key {request.idempotency_key!r} "
                            "reused with different arguments"
                        )
                    cached = ToolCallResult(
                        status="ok", tool_name=prior_result.tool_name,
                        version=prior_result.version, output=prior_result.output,
                        latency_ms=0.0, cost_usd=0.0, cached=True,
                        idempotency_key=request.idempotency_key,
                    )
                    self._audit(agent, tool, "ok", "idempotent-replay", 0.0, 0.0,
                                request.idempotency_key, args_hash)
                    return cached
            if tool.risk.requires_approval:
                approval = self._consume_approval(request, tool, args_hash)
                if approval is None:
                    approval_id = uuid.uuid4().hex
                    self._approvals[approval_id] = Approval(
                        approval_id=approval_id, agent_id=agent.agent_id,
                        tenant_id=agent.tenant_id, tool_name=tool.name,
                        version=tool.version, arguments_hash=args_hash,
                    )
                    raise ApprovalRequired(
                        f"{tool.name} requires approval (risk={tool.risk.value})",
                        approval_id,
                    )
            rate_key = f"{tool.key}|{agent.agent_id}|{agent.tenant_id}"
            if not self.rate_limiter.allow(rate_key, tool.rate_limit_per_minute):
                raise RateLimited(f"rate limit exceeded for {tool.key}")
            executor = self.executors.get(tool.name)
            if executor is None:
                raise ToolExecutionError(f"no executor registered for {tool.name}")
            output = self._run_with_timeout(executor, request.arguments,
                                            tool.timeout_seconds)
            output_errors = validate(output, tool.output_schema)
            if output_errors:
                raise ToolExecutionError(
                    "executor output failed schema validation: "
                    + "; ".join(output_errors)
                )
            latency_ms = (time.monotonic() - started) * 1000.0
            result = ToolCallResult(
                status="ok", tool_name=tool.name, version=tool.version,
                output=output, latency_ms=latency_ms,
                cost_usd=tool.cost_usd_per_call,
                idempotency_key=request.idempotency_key,
            )
            self.ledger.record(
                tool_name=tool.name, agent_id=agent.agent_id,
                tenant_id=agent.tenant_id, latency_ms=latency_ms,
                cost_usd=tool.cost_usd_per_call,
            )
            self._audit(agent, tool, "ok", "executed", latency_ms,
                        tool.cost_usd_per_call, request.idempotency_key, args_hash)
            if request.idempotency_key:
                self._idempotent[request.idempotency_key] = (args_hash, result)
            return result
        except (ApprovalRequired, IdempotencyConflict, RateLimited,
                Unauthorized, ValidationError, ToolExecutionError,
                ToolTimeout, ToolNotFound) as exc:
            latency_ms = (time.monotonic() - started) * 1000.0
            name = tool.name if tool else request.tool_name
            version = tool.version if tool else request.version
            self._audit(agent, tool, "denied" if isinstance(
                exc, (Unauthorized, RateLimited, ApprovalRequired)) else "error",
                type(exc).__name__, latency_ms, 0.0,
                request.idempotency_key,
                hash_arguments(request.arguments))
            raise

    def _consume_approval(self, request: ToolCallRequest, tool, args_hash):
        if not request.approval_id:
            return None
        approval = self._approvals.get(request.approval_id)
        if (
            approval is None
            or approval.status != "approved"
            or approval.agent_id != request.agent.agent_id
            or approval.tool_name != tool.name
            or approval.arguments_hash != args_hash
        ):
            return None
        approval.status = "consumed"
        return approval

    @staticmethod
    def _run_with_timeout(executor, arguments: dict, timeout: float) -> dict:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(executor, arguments)
            try:
                return future.result(timeout=timeout)
            except TimeoutError as exc:
                raise ToolTimeout(
                    f"executor exceeded timeout of {timeout}s"
                ) from exc
            except Exception as exc:
                raise ToolExecutionError(
                    f"executor failed: {exc}"
                ) from exc

    def _audit(self, agent: AgentIdentity, tool, decision: str, reason: str,
               latency_ms: float, cost_usd: float,
               idempotency_key, args_hash: str) -> None:
        self.audit.append(
            timestamp=_now(),
            agent_id=agent.agent_id,
            tenant_id=agent.tenant_id,
            tool_name=tool.name if tool else "?",
            version=tool.version if tool else "?",
            decision=decision,
            reason=reason,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            idempotency_key=idempotency_key,
            arguments_hash=args_hash,
        )


def build_default_gateway() -> ToolGateway:
    """Gateway wired with the default tool catalog and mock executors."""
    from .definitions import DEFAULT_TOOLS
    from .executors import EXECUTORS

    registry = ToolRegistry()
    for definition in DEFAULT_TOOLS:
        registry.register(definition)
    tenants = {
        "tenant-a": TenantPolicy(
            tenant_id="tenant-a",
            allowed_scopes=frozenset({
                "tools:calculator", "tools:echo", "tools:weather",
                "tools:summarize", "tools:kv", "tools:export",
            }),
        ),
        "tenant-b": TenantPolicy(
            tenant_id="tenant-b",
            allowed_scopes=frozenset({"tools:echo", "tools:weather"}),
        ),
    }
    return ToolGateway(registry, dict(EXECUTORS), tenants)
