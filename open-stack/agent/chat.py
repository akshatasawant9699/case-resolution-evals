"""Chat with agent v0 in the terminal, against a fresh copy of the seeded store.

    uv run python -m agent.chat --task refund-over-500-requires-approval   # a task's scenario
    uv run python -m agent.chat --customer CUS-0001                         # any seeded customer

Tool calls print as they happen. Commands: /state shows refunds and the case, /quit exits.
Each session gets its own temporary database, so nothing you do persists.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

from agent.backends import make_completion
from agent.v0 import ChatSession
from mcp_servers.db import build_database


def scenario(task_id: str | None, customer_id: str | None) -> tuple[dict, str, str, str]:
    """Return (fixtures, customer_id, case_id, opening line suggestion)."""
    if task_id:
        from evals.harness import load_tasks
        task = load_tasks([task_id])[0]
        return (task.get("fixtures", {}), task["context"]["customer_id"], task["context"]["case_id"],
                task["conversation"][0]["user"])
    customer_id = customer_id or "CUS-0001"
    case = {"id": "CASE-DEMO", "customer_id": customer_id, "order_id": None, "subject": "Demo chat",
            "status": "open", "created_at": "2026-11-20", "updated_at": "2026-11-20"}
    return {"cases": [case]}, customer_id, "CASE-DEMO", ""


def show_state(db: str, case_id: str) -> None:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        refunds = conn.execute("SELECT id, order_id, amount, refund_method, return_channel FROM refunds "
                               "WHERE created_by = 'agent'").fetchall()
        case = conn.execute("SELECT status FROM cases WHERE id = ?", (case_id,)).fetchone()
        notes = conn.execute("SELECT body FROM case_notes WHERE case_id = ?", (case_id,)).fetchall()
    print(f"  case {case_id}: {case['status']}")
    print("  refunds issued this session:", [dict(r) for r in refunds] or "none")
    for n in notes:
        print("  note:", n["body"])


async def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with agent v0.")
    parser.add_argument("--task", help="Load a spec task's scenario (fixtures, customer, case).")
    parser.add_argument("--customer", help="Chat as a seeded customer, e.g. CUS-0001.")
    parser.add_argument("--backend", choices=["gateway", "litellm"], default="gateway")
    parser.add_argument("--model")
    args = parser.parse_args()

    fixtures, customer_id, case_id, suggestion = scenario(args.task, args.customer)
    complete, model = make_completion(args.backend, args.model)
    with tempfile.TemporaryDirectory() as tmp:
        db = str(build_database(Path(tmp) / "chat.sqlite", fixtures))
        print(f"Agent v0 ({model}). You are {customer_id}, case {case_id}. /state, /quit.")
        if suggestion:
            print(f"Task opening line: {suggestion}")
        async with ChatSession(db, customer_id, case_id, complete) as session:
            while True:
                try:
                    text = input("\nyou> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if text in ("/quit", "/exit"):
                    break
                if text == "/state":
                    show_state(db, case_id)
                    continue
                if not text:
                    continue
                seen = len(session.state["tool_calls"])
                reply = await session.send(text)
                for call in session.state["tool_calls"][seen:]:
                    flag = "  [error]" if call["is_error"] else ""
                    print(f"  -> {call['tool']}({json.dumps(call['args'])}){flag}")
                print(f"\nagent> {reply}")


if __name__ == "__main__":
    asyncio.run(main())
