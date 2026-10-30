"""Default tool catalog: versioned definitions for the mock executors."""

from __future__ import annotations

from .models import RiskTier, ToolDefinition

OBJECT = {"type": "object", "additionalProperties": False}


def _schema(properties: dict, required: list[str]) -> dict:
    return {**OBJECT, "properties": properties, "required": required}


DEFAULT_TOOLS = [
    ToolDefinition(
        name="calculator", version="1.0.0",
        description="Deterministic arithmetic over two operands.",
        input_schema=_schema({
            "op": {"type": "string", "enum": ["add", "sub", "mul", "div"]},
            "a": {"type": "number"}, "b": {"type": "number"},
        }, ["op", "a", "b"]),
        output_schema=_schema({"result": {"type": "number"}}, ["result"]),
        scopes=("tools:calculator",), risk=RiskTier.LOW,
        rate_limit_per_minute=120, timeout_seconds=5.0, cost_usd_per_call=0.001,
    ),
    ToolDefinition(
        name="echo", version="1.0.0",
        description="Echoes a message back; the lowest-risk smoke-test tool.",
        input_schema=_schema({"message": {"type": "string", "maxLength": 500}},
                             ["message"]),
        output_schema=_schema({"message": {"type": "string"}}, ["message"]),
        scopes=("tools:echo",), risk=RiskTier.LOW,
        rate_limit_per_minute=120, timeout_seconds=5.0, cost_usd_per_call=0.0,
    ),
    ToolDefinition(
        name="weather_lookup", version="1.0.0",
        description="Synthetic weather for a small fixed set of fictional cities.",
        input_schema=_schema({"city": {"type": "string"}}, ["city"]),
        output_schema=_schema({
            "city": {"type": "string"}, "condition": {"type": "string"},
            "temp_c": {"type": "number"},
        }, ["city", "condition", "temp_c"]),
        scopes=("tools:weather",), risk=RiskTier.LOW,
        rate_limit_per_minute=60, timeout_seconds=5.0, cost_usd_per_call=0.002,
    ),
    ToolDefinition(
        name="text_summarize", version="1.0.0",
        description="Extractive summary: keeps the first N sentences, verbatim.",
        input_schema=_schema({
            "text": {"type": "string", "minLength": 1},
            "max_sentences": {"type": "integer", "minimum": 1, "maximum": 10},
        }, ["text", "max_sentences"]),
        output_schema=_schema({"summary": {"type": "string"}}, ["summary"]),
        scopes=("tools:summarize",), risk=RiskTier.MEDIUM,
        rate_limit_per_minute=60, timeout_seconds=10.0, cost_usd_per_call=0.005,
    ),
    ToolDefinition(
        name="kv_store", version="1.0.0",
        description="In-memory key/value store scoped to the gateway process.",
        input_schema=_schema({
            "op": {"type": "string", "enum": ["get", "put", "delete"]},
            "key": {"type": "string"},
            "value": {"type": "string"},
        }, ["op", "key"]),
        output_schema={"type": "object"},
        scopes=("tools:kv",), risk=RiskTier.MEDIUM,
        rate_limit_per_minute=120, timeout_seconds=5.0, cost_usd_per_call=0.001,
    ),
    ToolDefinition(
        name="data_export", version="1.0.0",
        description="HIGH-RISK: exports synthetic rows. Requires human approval.",
        input_schema=_schema({
            "row_limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "format": {"type": "string", "enum": ["json", "csv"]},
        }, ["row_limit", "format"]),
        output_schema=_schema({
            "exported_rows": {"type": "integer"}, "format": {"type": "string"},
            "rows": {"type": "array"},
        }, ["exported_rows", "format", "rows"]),
        scopes=("tools:export",), risk=RiskTier.HIGH,
        rate_limit_per_minute=10, timeout_seconds=30.0, cost_usd_per_call=0.05,
    ),
    ToolDefinition(
        name="slow_echo", version="1.0.0",
        description="Echo after a delay; used to exercise gateway timeouts.",
        input_schema=_schema({
            "message": {"type": "string"},
            "sleep_seconds": {"type": "number", "minimum": 0, "maximum": 30},
        }, ["message", "sleep_seconds"]),
        output_schema=_schema({"message": {"type": "string"}}, ["message"]),
        scopes=("tools:echo",), risk=RiskTier.LOW,
        rate_limit_per_minute=60, timeout_seconds=0.2, cost_usd_per_call=0.0,
    ),
]
