"""Ensure src/ is importable so plain `pytest` from the project dir passes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from agent_tool_gateway import AgentIdentity, build_default_gateway

ALL_SCOPES = frozenset({
    "tools:calculator", "tools:echo", "tools:weather",
    "tools:summarize", "tools:kv", "tools:export",
})


@pytest.fixture()
def gateway():
    return build_default_gateway()


@pytest.fixture()
def agent():
    return AgentIdentity(agent_id="agent-1", tenant_id="tenant-a",
                         scopes=ALL_SCOPES)


@pytest.fixture()
def limited_agent():
    return AgentIdentity(agent_id="agent-2", tenant_id="tenant-b",
                         scopes=frozenset({"tools:echo", "tools:weather"}))
