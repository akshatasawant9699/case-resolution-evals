"""Run the spec tasks against agent v0 and save one JSONL trace line per trial.

    uv run python -m evals.run                      # every task, 1 trial
    uv run python -m evals.run --trials 3 --task no-duplicate-refund

Backends:
  --backend litellm (default)  needs a provider key, e.g. ANTHROPIC_API_KEY; model from --model/AGENT_MODEL
  --backend gateway            reuses Claude Code's Bedrock gateway (see agent/gateway.py)

Trials run concurrently (--concurrency, default 4); each has its own database.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from agent.backends import make_completion
from agent.v0 import CompletionFn
from evals.harness import load_tasks, run_trial

RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"


def new_trace_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RUNS_DIR / f"v0-{stamp}.jsonl"


def format_result(result: dict) -> str:
    mark = "PASS" if result["passed"] else "ERROR" if result["error"] else "FAIL"
    detail = result["error"] or "; ".join(c["check"] for c in result["checks"] if not c["passed"])
    return f"{mark}  {result['task_id']} #{result['trial']}" + (f"  {detail}" if detail else "")


def summarize(results: list[dict], out: Path) -> str:
    passed = sum(r["passed"] for r in results)
    errors = sum(r["error"] is not None for r in results)
    cost = sum(r["usage"]["cost_usd"] for r in results)
    note = f" ({errors} errored: not a valid measurement of the agent)" if errors else ""
    return f"{passed}/{len(results)} trials passed{note}, ${cost:.4f}. Traces: {out}"


async def run_suite(tasks: list[dict], trials: int, complete: CompletionFn, model: str, out: Path,
                    concurrency: int = 4, on_result: Callable[[dict], None] = print) -> list[dict]:
    """Run every (task, trial) with bounded concurrency, appending each trace to `out` as it lands."""
    out.parent.mkdir(parents=True, exist_ok=True)
    gate = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    with out.open("w") as f:
        async def one(task: dict, trial: int) -> None:
            async with gate:
                result = await run_trial(task, trial, complete, model)
            f.write(json.dumps(result, default=str) + "\n")
            f.flush()
            results.append(result)
            on_result(result)

        await asyncio.gather(*(one(t, i) for t in tasks for i in range(trials)))
    order = {t["id"]: n for n, t in enumerate(tasks)}
    return sorted(results, key=lambda r: (order[r["task_id"]], r["trial"]))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run spec tasks against agent v0.")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--task", action="append", help="Task id; repeat for several. Default: all.")
    parser.add_argument("--backend", choices=["litellm", "gateway"], default="litellm")
    parser.add_argument("--model", help="Default: AGENT_MODEL for litellm, claude-opus-5-5 for gateway.")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    tasks = load_tasks(args.task)
    complete, model = make_completion(args.backend, args.model)
    out = args.out or new_trace_path()
    results = await run_suite(tasks, args.trials, complete, model, out, args.concurrency,
                              lambda r: print(format_result(r), flush=True))
    print("\n" + summarize(results, out))


if __name__ == "__main__":
    asyncio.run(main())
