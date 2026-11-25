"""Run the spec tasks against agent v0 and save one JSONL trace line per trial.

    uv run python -m evals.run                      # every task, 1 trial
    uv run python -m evals.run --trials 3 --task no-duplicate-refund

Backends:
  --backend litellm (default)  needs a provider key, e.g. ANTHROPIC_API_KEY; model from --model/AGENT_MODEL
  --backend gateway            reuses Claude Code's Bedrock gateway (see agent/gateway.py)
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from agent.backends import make_completion
from evals.harness import load_tasks, run_trial

RUNS_DIR = Path(__file__).resolve().parents[1] / "runs"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run spec tasks against agent v0.")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--task", action="append", help="Task id; repeat for several. Default: all.")
    parser.add_argument("--backend", choices=["litellm", "gateway"], default="litellm")
    parser.add_argument("--model", help="Default: AGENT_MODEL for litellm, the Bedrock Opus ID for gateway.")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    tasks = load_tasks(args.task)
    complete, args.model = make_completion(args.backend, args.model)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or RUNS_DIR / f"v0-{stamp}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    passed = total = errors = 0
    cost = 0.0
    with out.open("w") as f:
        for task in tasks:
            for trial in range(args.trials):
                result = await run_trial(task, trial, complete, args.model)
                f.write(json.dumps(result, default=str) + "\n")
                f.flush()
                passed += result["passed"]
                total += 1
                cost += result["usage"]["cost_usd"]
                failed = [c["check"] for c in result["checks"] if not c["passed"]]
                errors += result["error"] is not None
                mark = "PASS" if result["passed"] else "ERROR" if result["error"] else "FAIL"
                detail = result["error"] or "; ".join(failed)
                print(f"{mark}  {task['id']} #{trial}" + (f"  {detail}" if detail else ""))
    note = f" ({errors} errored: not a valid measurement of the agent)" if errors else ""
    print(f"\n{passed}/{total} trials passed{note}, ${cost:.4f}. Traces: {out}")


if __name__ == "__main__":
    asyncio.run(main())
