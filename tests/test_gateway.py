import pytest

from agent_tool_gateway import (
    AgentIdentity,
    ApprovalRequired,
    IdempotencyConflict,
    RateLimited,
    ToolCallRequest,
    ToolExecutionError,
    ToolNotFound,
    ToolTimeout,
    Unauthorized,
    ValidationError,
)


def call(gateway, agent, tool, args, **kw):
    return gateway.execute(ToolCallRequest(
        agent=agent, tool_name=tool, arguments=args, **kw))


def test_happy_path_calculator(gateway, agent):
    result = call(gateway, agent, "calculator", {"op": "add", "a": 2, "b": 3})
    assert result.status == "ok" and result.output == {"result": 5}
    assert result.cost_usd == 0.001 and not result.cached


def test_unknown_tool_fails_closed(gateway, agent):
    with pytest.raises(ToolNotFound):
        call(gateway, agent, "nope", {})


def test_missing_scope_denied(gateway, limited_agent):
    with pytest.raises(Unauthorized):
        call(gateway, limited_agent, "calculator", {"op": "add", "a": 1, "b": 1})


def test_tenant_scope_allowlist_denied(gateway):
    # tenant-b allows echo/weather only, even if the agent claims more.
    agent = AgentIdentity(agent_id="a3", tenant_id="tenant-b",
                          scopes=frozenset({"tools:calculator"}))
    with pytest.raises(Unauthorized):
        call(gateway, agent, "calculator", {"op": "add", "a": 1, "b": 1})


def test_unknown_tenant_denied(gateway, agent):
    stranger = AgentIdentity(agent_id="a9", tenant_id="tenant-zzz",
                             scopes=frozenset({"tools:echo"}))
    with pytest.raises(Unauthorized):
        call(gateway, stranger, "echo", {"message": "hi"})


def test_invalid_arguments_rejected(gateway, agent):
    with pytest.raises(ValidationError):
        call(gateway, agent, "calculator", {"op": "add", "a": 1})
    with pytest.raises(ValidationError):
        call(gateway, agent, "calculator", {"op": "pow", "a": 1, "b": 2})


def test_executor_error_surfaced(gateway, agent):
    with pytest.raises(ToolExecutionError):
        call(gateway, agent, "calculator", {"op": "div", "a": 1, "b": 0})


def test_idempotent_replay_returns_cached(gateway, agent):
    args = {"op": "mul", "a": 3, "b": 4}
    first = call(gateway, agent, "calculator", args, idempotency_key="k-1")
    second = call(gateway, agent, "calculator", args, idempotency_key="k-1")
    assert second.cached and second.output == first.output
    assert second.cost_usd == 0.0
    # Same key, different payload -> conflict, never silent overwrite.
    with pytest.raises(IdempotencyConflict):
        call(gateway, agent, "calculator", {"op": "mul", "a": 3, "b": 5},
             idempotency_key="k-1")


def test_high_risk_approval_flow(gateway, agent):
    args = {"row_limit": 3, "format": "json"}
    with pytest.raises(ApprovalRequired) as exc_info:
        call(gateway, agent, "data_export", args)
    approval_id = exc_info.value.approval_id
    assert gateway.pending_approvals()
    gateway.approve(approval_id, approver="human-1")
    result = call(gateway, agent, "data_export", args, approval_id=approval_id)
    assert result.output["exported_rows"] == 3
    # Approval is one-shot: reuse must not work.
    with pytest.raises(ApprovalRequired):
        call(gateway, agent, "data_export", args, approval_id=approval_id)


def test_rejected_approval_cannot_run(gateway, agent):
    args = {"row_limit": 2, "format": "csv"}
    with pytest.raises(ApprovalRequired) as exc_info:
        call(gateway, agent, "data_export", args)
    gateway.reject(exc_info.value.approval_id, approver="human-1")
    with pytest.raises(ApprovalRequired):
        call(gateway, agent, "data_export", args,
             approval_id=exc_info.value.approval_id)


def test_rate_limit_exhausts(gateway, agent):
    # slow_echo has a 60/min limit shared per agent; use a tiny-limit tool
    # via direct bucket behaviour instead: exhaust calculator is too slow,
    # so verify the limiter unit below and here check denial path exists
    # by registering a 1/min tool through the registry.
    from agent_tool_gateway import ToolDefinition, RiskTier
    gateway.registry.register(ToolDefinition(
        name="tiny_tool", version="1.0.0", description="t",
        input_schema={"type": "object"}, output_schema={"type": "object"},
        scopes=("tools:echo",), risk=RiskTier.LOW, rate_limit_per_minute=1,
        timeout_seconds=5.0))
    gateway.executors["tiny_tool"] = lambda args: {"ok": True}
    call(gateway, agent, "tiny_tool", {})
    with pytest.raises(RateLimited):
        call(gateway, agent, "tiny_tool", {})


def test_timeout_enforced(gateway, agent):
    with pytest.raises(ToolTimeout):
        call(gateway, agent, "slow_echo",
             {"message": "hi", "sleep_seconds": 5})


def test_denials_are_audited(gateway, limited_agent):
    with pytest.raises(Unauthorized):
        call(gateway, limited_agent, "calculator",
             {"op": "add", "a": 1, "b": 1})
    denied = [e for e in gateway.audit.entries() if e.decision == "denied"]
    assert denied and denied[-1].tool_name == "calculator"
    assert gateway.audit.verify()
