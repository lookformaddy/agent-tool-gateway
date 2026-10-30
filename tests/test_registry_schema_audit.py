import pytest

from agent_tool_gateway import (
    RiskTier,
    ToolDefinition,
    ToolNotFound,
    ToolRegistry,
)
from agent_tool_gateway.audit import AuditLog
from agent_tool_gateway.schema import validate


def test_registry_versioning():
    registry = ToolRegistry()
    v1 = ToolDefinition(name="t", version="1.0.0", description="",
                        input_schema={}, output_schema={})
    v2 = ToolDefinition(name="t", version="2.0.0", description="",
                        input_schema={}, output_schema={})
    registry.register(v1)
    registry.register(v2)
    assert registry.get("t").version == "2.0.0"
    assert registry.get("t", "1.0.0").version == "1.0.0"
    assert registry.versions_of("t") == ["1.0.0", "2.0.0"]
    with pytest.raises(ToolNotFound):
        registry.get("t", "9.9.9")
    with pytest.raises(ValueError):
        registry.register(v1)


def test_risk_tier_approval_gate():
    assert RiskTier.HIGH.requires_approval
    assert RiskTier.CRITICAL.requires_approval
    assert not RiskTier.LOW.requires_approval
    assert not RiskTier.MEDIUM.requires_approval


def test_schema_validation():
    schema = {"type": "object", "properties": {
        "n": {"type": "integer", "minimum": 1, "maximum": 5},
        "s": {"type": "string", "enum": ["a", "b"]},
    }, "required": ["n"], "additionalProperties": False}
    assert validate({"n": 3, "s": "a"}, schema) == []
    assert validate({"s": "a"}, schema)  # missing required
    assert validate({"n": 0}, schema)  # below minimum
    assert validate({"n": 3, "s": "c"}, schema)  # enum violation
    assert validate({"n": 3, "x": 1}, schema)  # additional property
    assert validate({"n": True}, schema)  # bool is not an integer


def test_audit_chain_verifies_and_detects_tampering():
    log = AuditLog()
    log.append(timestamp="2026-01-01T00:00:00+00:00", agent_id="a",
               tenant_id="t", tool_name="echo", version="1.0.0",
               decision="ok", reason="executed", latency_ms=1.0, cost_usd=0.0)
    log.append(timestamp="2026-01-01T00:00:01+00:00", agent_id="a",
               tenant_id="t", tool_name="echo", version="1.0.0",
               decision="denied", reason="Unauthorized", latency_ms=0.0,
               cost_usd=0.0)
    assert log.verify()
    entries = log.entries()
    entries[0].decision = "denied"  # tamper with a stored entry
    assert not log.verify()
