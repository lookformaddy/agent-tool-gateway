"""Cost and latency accounting, aggregated per tool / agent / tenant."""

from __future__ import annotations

from collections import defaultdict


class CostLedger:
    def __init__(self) -> None:
        self._cost_by_tool: defaultdict[str, float] = defaultdict(float)
        self._cost_by_agent: defaultdict[str, float] = defaultdict(float)
        self._cost_by_tenant: defaultdict[str, float] = defaultdict(float)
        self._calls_by_tool: defaultdict[str, int] = defaultdict(int)
        self._latency_by_tool: defaultdict[str, list[float]] = defaultdict(list)

    def record(
        self, *, tool_name: str, agent_id: str, tenant_id: str,
        latency_ms: float, cost_usd: float,
    ) -> None:
        self._cost_by_tool[tool_name] += cost_usd
        self._cost_by_agent[agent_id] += cost_usd
        self._cost_by_tenant[tenant_id] += cost_usd
        self._calls_by_tool[tool_name] += 1
        self._latency_by_tool[tool_name].append(latency_ms)

    def summary(self) -> dict:
        avg_latency = {
            tool: (sum(v) / len(v) if v else 0.0)
            for tool, v in self._latency_by_tool.items()
        }
        return {
            "total_cost_usd": round(sum(self._cost_by_tool.values()), 6),
            "cost_by_tool": dict(self._cost_by_tool),
            "cost_by_agent": dict(self._cost_by_agent),
            "cost_by_tenant": dict(self._cost_by_tenant),
            "calls_by_tool": dict(self._calls_by_tool),
            "avg_latency_ms_by_tool": avg_latency,
        }
