from agent_tool_gateway import ToolCallRequest
from agent_tool_gateway.accounting import CostLedger
from agent_tool_gateway.executors import EXECUTORS
from agent_tool_gateway.rate_limit import TokenBucket


def test_executors_deterministic():
    assert EXECUTORS["calculator"]({"op": "sub", "a": 10, "b": 4}) == {"result": 6}
    assert EXECUTORS["weather_lookup"]({"city": "Riverton"})["temp_c"] == 14
    assert EXECUTORS["text_summarize"](
        {"text": "One. Two. Three.", "max_sentences": 2}
    ) == {"summary": "One. Two."}
    EXECUTORS["kv_store"]({"op": "put", "key": "k", "value": "v"})
    assert EXECUTORS["kv_store"]({"op": "get", "key": "k"})["value"] == "v"
    assert EXECUTORS["data_export"](
        {"row_limit": 2, "format": "json"})["exported_rows"] == 2


def test_token_bucket_refill_disabled_is_deterministic():
    bucket = TokenBucket(capacity=2, refill_per_second=0.0)
    assert bucket.allow() and bucket.allow() and not bucket.allow()


def test_ledger_aggregation(gateway, agent):
    gateway.execute(ToolCallRequest(agent=agent, tool_name="calculator",
                                    arguments={"op": "add", "a": 1, "b": 2}))
    gateway.execute(ToolCallRequest(agent=agent, tool_name="weather_lookup",
                                    arguments={"city": "Springfield"}))
    summary = gateway.ledger.summary()
    assert summary["calls_by_tool"] == {"calculator": 1, "weather_lookup": 1}
    assert summary["total_cost_usd"] == round(0.001 + 0.002, 6)
    assert summary["cost_by_tenant"]["tenant-a"] == round(0.003, 6)
