"""Deterministic mock tool executors. No network, no randomness, no I/O.

These stand in for real downstream tools so the gateway's authorization,
approval, rate-limit, idempotency, timeout and audit behavior can be
exercised end to end. A production deployment swaps an executor for a
real client behind the same (arguments -> output dict) signature.
"""

from __future__ import annotations

import time

# Static synthetic reference data (invented, not from any real system).
_WEATHER = {
    "springfield": {"city": "Springfield", "condition": "sunny", "temp_c": 22},
    "riverton": {"city": "Riverton", "condition": "rainy", "temp_c": 14},
    "lakeside": {"city": "Lakeside", "condition": "cloudy", "temp_c": 18},
}


def calculator(args: dict) -> dict:
    op, a, b = args["op"], args["a"], args["b"]
    if op == "add":
        result = a + b
    elif op == "sub":
        result = a - b
    elif op == "mul":
        result = a * b
    elif op == "div":
        if b == 0:
            raise ValueError("division by zero")
        result = a / b
    else:
        raise ValueError(f"unknown op: {op}")
    return {"result": result}


def echo(args: dict) -> dict:
    return {"message": args["message"]}


def weather_lookup(args: dict) -> dict:
    city = args["city"].lower()
    if city not in _WEATHER:
        raise ValueError(f"no weather data for city: {args['city']}")
    return dict(_WEATHER[city])


def text_summarize(args: dict) -> dict:
    sentences = [s.strip() for s in args["text"].split(".") if s.strip()]
    kept = sentences[: args["max_sentences"]]
    return {"summary": ". ".join(kept) + ("." if kept else "")}


def _kv_store() -> dict:
    return {}


_KV: dict[str, str] = {}


def kv_store(args: dict) -> dict:
    op = args["op"]
    if op == "put":
        _KV[args["key"]] = args["value"]
        return {"stored": True, "key": args["key"]}
    if op == "get":
        return {"key": args["key"], "value": _KV.get(args["key"])}
    if op == "delete":
        existed = _KV.pop(args["key"], None) is not None
        return {"deleted": existed, "key": args["key"]}
    raise ValueError(f"unknown kv op: {op}")


def data_export(args: dict) -> dict:
    """High-risk mock: pretends to export N synthetic rows, deterministically."""
    rows = args["row_limit"]
    return {"exported_rows": rows, "format": args["format"], "rows": [
        {"id": i, "value": f"row-{i}"} for i in range(rows)
    ]}


def slow_echo(args: dict) -> dict:
    time.sleep(args["sleep_seconds"])
    return {"message": args["message"]}


EXECUTORS = {
    "calculator": calculator,
    "echo": echo,
    "weather_lookup": weather_lookup,
    "text_summarize": text_summarize,
    "kv_store": kv_store,
    "data_export": data_export,
    "slow_echo": slow_echo,
}
