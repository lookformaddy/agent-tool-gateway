"""End-to-end demo: allowed call, denial, approval gate, idempotency, audit.

Run:  python examples/run_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_tool_gateway import (
    AgentIdentity,
    ApprovalRequired,
    ToolCallRequest,
    Unauthorized,
    build_default_gateway,
)

ALL_SCOPES = frozenset({
    "tools:calculator", "tools:echo", "tools:weather",
    "tools:summarize", "tools:kv", "tools:export",
})


def main() -> None:
    gateway = build_default_gateway()
    agent = AgentIdentity(agent_id="demo-agent", tenant_id="tenant-a",
                          scopes=ALL_SCOPES)

    result = gateway.execute(ToolCallRequest(
        agent=agent, tool_name="calculator",
        arguments={"op": "mul", "a": 6, "b": 7}))
    print(f"calculator 6*7 -> {result.output} (cost ${result.cost_usd})")

    limited = AgentIdentity(agent_id="demo-limited", tenant_id="tenant-b",
                            scopes=frozenset({"tools:echo"}))
    try:
        gateway.execute(ToolCallRequest(
            agent=limited, tool_name="calculator",
            arguments={"op": "add", "a": 1, "b": 1}))
    except Unauthorized as exc:
        print(f"denied as expected (fail-closed): {exc}")

    export_args = {"row_limit": 3, "format": "json"}
    try:
        gateway.execute(ToolCallRequest(
            agent=agent, tool_name="data_export", arguments=export_args))
    except ApprovalRequired as exc:
        print(f"approval gate triggered: approval_id={exc.approval_id}")
        gateway.approve(exc.approval_id, approver="demo-human")
        approved = gateway.execute(ToolCallRequest(
            agent=agent, tool_name="data_export", arguments=export_args,
            approval_id=exc.approval_id))
        print(f"data_export after approval -> {approved.output['exported_rows']} rows")

    replay_args = {"op": "add", "a": 40, "b": 2}
    first = gateway.execute(ToolCallRequest(
        agent=agent, tool_name="calculator", arguments=replay_args,
        idempotency_key="demo-key-1"))
    replay = gateway.execute(ToolCallRequest(
        agent=agent, tool_name="calculator", arguments=replay_args,
        idempotency_key="demo-key-1"))
    print(f"idempotent replay: cached={replay.cached}, output={replay.output} "
          f"(first cost ${first.cost_usd}, replay cost ${replay.cost_usd})")

    print(f"audit chain valid: {gateway.audit.verify()} "
          f"({len(gateway.audit.entries())} entries)")
    print(f"ledger: {gateway.ledger.summary()}")


if __name__ == "__main__":
    main()
