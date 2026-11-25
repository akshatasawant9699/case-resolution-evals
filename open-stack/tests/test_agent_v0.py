"""Agent v0 and the eval harness, driven by a scripted fake model (no API key needed)."""

import json

from agent import v0
from evals.harness import check_forbidden, check_state, load_tasks, run_trial
from mcp_servers.db import build_database


def scripted(*steps):
    """A fake completion_fn that plays back steps: a list of (tool, args) calls, or a final reply."""
    seen = []

    async def complete(messages, tools):
        seen.append({"messages": list(messages), "tools": tools})
        step = steps[len(seen) - 1]
        usage = {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.001}
        if isinstance(step, str):
            return {"role": "assistant", "content": step}, usage
        calls = [{"id": f"call_{len(seen)}_{i}", "type": "function",
                  "function": {"name": name, "arguments": json.dumps(args)}}
                 for i, (name, args) in enumerate(step)]
        return {"role": "assistant", "content": "", "tool_calls": calls}, usage

    complete.seen = seen
    return complete


TASK = next(t for t in load_tasks() if t["id"] == "refund-over-500-requires-approval")


async def test_agent_sees_every_tool_and_a_thin_prompt():
    fake = scripted("Hello.")
    await run_trial(TASK, 0, fake, "fake")
    first = fake.seen[0]
    assert {t["function"]["name"] for t in first["tools"]} == {
        "get_order", "list_orders", "issue_refund", "update_case", "add_case_note"}
    system = first["messages"][0]["content"]
    assert "CUS-T005" in system and "CASE-T005" in system and "2026-11-20" in system
    assert "refund" not in system.lower(), "v0 prompt must not carry policy"


async def test_naive_refund_fails_the_task():
    fake = scripted(
        [("get_order", {"order_id": "ORD-T005"})],
        [("issue_refund", {"order_id": "ORD-T005", "amount": 742.5, "reason": "changed_mind",
                           "refund_method": "card", "return_channel": "mail"})],
        "Done, your refund of $742.50 is on its way.",
    )
    result = await run_trial(TASK, 0, fake, "fake")
    assert not result["passed"]
    assert [c["passed"] for c in result["checks"]] == [False, False, False]
    assert [c["tool"] for c in result["tool_calls"]] == ["get_order", "issue_refund"]
    assert result["usage"] == {"model_calls": 3, "input_tokens": 30, "output_tokens": 15, "cost_usd": 0.003}


async def test_escalating_passes_the_task():
    fake = scripted(
        [("get_order", {"order_id": "ORD-T005"})],
        [("update_case", {"case_id": "CASE-T005", "status": "escalated"}),
         ("add_case_note", {"case_id": "CASE-T005", "body": "Refund over $500 needs approval."})],
        "I've sent this to a supervisor for approval.",
    )
    result = await run_trial(TASK, 0, fake, "fake")
    assert result["passed"], result["checks"]
    assert result["messages"][-1]["content"].startswith("I've sent")


async def test_tool_errors_go_back_to_the_model():
    fake = scripted([("get_order", {"order_id": "ORD-NOPE"})], "I couldn't find that order.")
    result = await run_trial(TASK, 0, fake, "fake")
    assert result["tool_calls"][0]["is_error"]
    assert "not found" in fake.seen[1]["messages"][-1]["content"]


async def test_a_crash_is_a_failed_trial():
    async def boom(messages, tools):
        raise RuntimeError("model unavailable")
    result = await run_trial(TASK, 0, boom, "fake")
    assert not result["passed"] and "model unavailable" in result["error"]


def test_check_state_operators(tmp_path):
    db = build_database(tmp_path / "t.sqlite")
    r = check_state(db, [
        {"table": "customers", "where": {}, "count": 50},
        {"table": "refunds", "where": {}, "count_gte": 30},
        {"table": "refunds", "where": {"order_id": "ORD-NOPE"}, "field": "amount", "sum_eq": 0},
        {"table": "refunds", "where": {"order_id": "ORD-NOPE"}, "field": "status", "in": ["pending"]},
    ])
    assert [c["passed"] for c in r] == [True, True, True, False]


def test_check_forbidden_matches_arg_subset():
    calls = [{"tool": "issue_refund", "args": {"order_id": "ORD-1", "amount": 5}, "is_error": True}]
    assert not check_forbidden(calls, [{"tool": "issue_refund", "args": {"order_id": "ORD-1"}}])[0]["passed"]
    assert check_forbidden(calls, [{"tool": "issue_refund", "args": {"order_id": "ORD-2"}}])[0]["passed"]
    assert not check_forbidden(calls, [{"tool": "issue_refund"}])[0]["passed"]


async def test_chat_session_keeps_history_across_turns(tmp_path):
    from agent.chat import scenario
    from agent.v0 import ChatSession
    fixtures, customer, case, opening = scenario(TASK["id"], None)
    assert (customer, case) == ("CUS-T005", "CASE-T005") and "742.50" in opening
    db = str(build_database(tmp_path / "c.sqlite", fixtures))
    fake = scripted([("get_order", {"order_id": "ORD-T005"})], "Looking into it.", "Still here.")
    async with ChatSession(db, customer, case, fake) as session:
        assert await session.send("first") == "Looking into it."
        assert await session.send("second") == "Still here."
    users = [m["content"] for m in fake.seen[-1]["messages"] if m["role"] == "user"]
    assert users == ["first", "second"]
    assert [c["tool"] for c in session.state["tool_calls"]] == ["get_order"]


def test_free_chat_scenario_has_a_case():
    from agent.chat import scenario
    fixtures, customer, case, _ = scenario(None, "CUS-0001")
    assert customer == "CUS-0001" and fixtures["cases"][0]["id"] == case


async def test_run_suite_runs_in_parallel_and_writes_traces(tmp_path):
    import asyncio
    import time
    from evals.run import run_suite

    async def slow(messages, tools):
        await asyncio.sleep(0.3)
        return {"role": "assistant", "content": "ok"}, {"input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

    tasks = load_tasks()[:4]
    seen = []
    start = time.perf_counter()
    results = await run_suite(tasks, 1, slow, "fake", tmp_path / "t.jsonl", concurrency=4, on_result=seen.append)
    assert time.perf_counter() - start < 1.0, "4 trials of 0.3s should overlap"
    assert [r["task_id"] for r in results] == [t["id"] for t in tasks]
    assert len(seen) == 4 and len((tmp_path / "t.jsonl").read_text().splitlines()) == 4
