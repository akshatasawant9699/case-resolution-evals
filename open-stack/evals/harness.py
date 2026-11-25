"""Run spec tasks against an agent and grade the final database state.

Each trial gets a fresh SQLite database (seeds + the task's fixtures), plays the task's
scripted conversation, then checks `expected_state` and `forbidden_actions`. A trial passes
only if every check passes.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import yaml

from agent import v0
from mcp_servers.db import REPO_ROOT, build_database

TASK_DIR = REPO_ROOT / "spec" / "tasks"
FIELD_OPS = ("equals", "in", "sum_eq", "sum_lte")


def load_tasks(ids: list[str] | None = None) -> list[dict]:
    tasks = [yaml.safe_load(p.read_text()) for p in sorted(TASK_DIR.glob("*.yaml"))]
    if ids:
        missing = set(ids) - {t["id"] for t in tasks}
        if missing:
            raise SystemExit(f"Unknown task ids: {sorted(missing)}")
        tasks = [t for t in tasks if t["id"] in ids]
    return tasks


def _describe(check: dict) -> str:
    where = ", ".join(f"{k}={v}" for k, v in check["where"].items())
    rest = {k: v for k, v in check.items() if k not in ("table", "where")}
    return f"{check['table']}[{where}] " + " ".join(f"{k}={v}" for k, v in rest.items())


def check_state(db_path: str | Path, checks: list[dict]) -> list[dict]:
    results = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for check in checks:
            where = check["where"]
            sql = f"SELECT * FROM {check['table']}"
            if where:
                sql += " WHERE " + " AND ".join(f"{col} = ?" for col in where)
            rows = [dict(r) for r in conn.execute(sql, list(where.values()))]
            field = check.get("field")
            values = [r[field] for r in rows] if field else []
            if "count" in check:
                ok, actual = len(rows) == check["count"], len(rows)
            elif "count_gte" in check:
                ok, actual = len(rows) >= check["count_gte"], len(rows)
            elif "equals" in check:
                ok, actual = bool(rows) and all(v == check["equals"] for v in values), values
            elif "in" in check:
                ok, actual = bool(rows) and all(v in check["in"] for v in values), values
            elif "sum_eq" in check:
                actual = round(sum(values), 2)
                ok = abs(actual - check["sum_eq"]) < 0.005
            elif "sum_lte" in check:
                actual = round(sum(values), 2)
                ok = actual <= check["sum_lte"] + 0.005
            else:
                raise ValueError(f"Check has no operator: {check}")
            results.append({"kind": "state", "check": _describe(check), "passed": ok, "actual": actual})
    return results


def check_forbidden(tool_calls: list[dict], forbidden: list[dict]) -> list[dict]:
    """A forbidden action matches any call to that tool whose args include the given subset.

    Attempts count even if the tool returned an error: the agent tried.
    """
    results = []
    for rule in forbidden:
        subset = rule.get("args", {})
        hits = [c for c in tool_calls
                if c["tool"] == rule["tool"] and all(c["args"].get(k) == v for k, v in subset.items())]
        results.append({"kind": "forbidden", "check": f"no {rule['tool']}({subset})",
                        "passed": not hits, "actual": [c["args"] for c in hits]})
    return results


async def run_trial(task: dict, trial: int, complete: v0.CompletionFn, model: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(build_database(Path(tmp) / "trial.sqlite", task.get("fixtures")))
        error = None
        try:
            state = await v0.run_conversation(
                db, task["context"]["customer_id"], task["context"]["case_id"],
                [turn["user"] for turn in task["conversation"]], complete)
        except Exception as exc:  # a crashed trial is a failed trial, not a crashed run
            state, error = {"messages": [], "tool_calls": [], "usage": []}, f"{type(exc).__name__}: {exc}"
        checks = check_state(db, task["expected_state"]) + check_forbidden(
            state["tool_calls"], task.get("forbidden_actions", []))
    usage = state["usage"]
    return {
        "task_id": task["id"], "trial": trial, "agent": "v0", "model": model,
        "passed": error is None and all(c["passed"] for c in checks),
        "error": error, "checks": checks,
        "tool_calls": state["tool_calls"], "messages": state["messages"],
        "usage": {"model_calls": len(usage),
                  "input_tokens": sum(u["input_tokens"] for u in usage),
                  "output_tokens": sum(u["output_tokens"] for u in usage),
                  "cost_usd": round(sum(u["cost_usd"] for u in usage), 6)},
    }
