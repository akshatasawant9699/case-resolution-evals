"""Message conversion for the Bedrock gateway backend (offline)."""

import json

from agent.gateway import from_anthropic, parse_headers, to_anthropic


def test_parse_headers():
    assert parse_headers("X-Key: a:b\nX-Other:  c \n\nbad") == {"X-Key": "a:b", "X-Other": "c"}


def test_round_trip_with_parallel_tool_results():
    call = lambda i: {"id": f"t{i}", "type": "function",
                      "function": {"name": "get_order", "arguments": json.dumps({"order_id": f"O{i}"})}}
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "", "tool_calls": [call(1), call(2)]},
        {"role": "tool", "tool_call_id": "t1", "content": "one"},
        {"role": "tool", "tool_call_id": "t2", "content": "two"},
    ]
    tools = [{"type": "function", "function": {"name": "get_order", "description": "d",
                                               "parameters": {"type": "object"}}}]
    body = to_anthropic(messages, tools)
    assert body["system"] == "Be helpful."
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert [b["tool_use_id"] for b in body["messages"][2]["content"]] == ["t1", "t2"]
    assert body["messages"][1]["content"][0] == {"type": "tool_use", "id": "t1", "name": "get_order",
                                                 "input": {"order_id": "O1"}}
    assert body["tools"][0]["input_schema"] == {"type": "object"}

    assistant, usage = from_anthropic({"content": [
        {"type": "text", "text": "Checking."},
        {"type": "tool_use", "id": "t3", "name": "list_orders", "input": {"customer_id": "C1"}}],
        "usage": {"input_tokens": 1000, "output_tokens": 100}}, "us.anthropic.claude-opus-5-5")
    assert assistant["content"] == "Checking."
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"customer_id": "C1"}
    assert usage == {"input_tokens": 1000, "output_tokens": 100, "cost_usd": 0.0075}
