# case-resolution-evals

An enterprise **case resolution agent** built with **evaluation-driven development (EDD)**:
capability evals are written before each feature, failures are found by reading traces, and a
CI gate blocks any change that lowers **pass^k** (the probability the agent succeeds on all *k*
tries, not just one).

> Status: **week 1 scaffold.** The task suite and the v0 agent are next.

## The EDD loop (run every week)

1. **Specify** — write capability evals for the feature before building it.
2. **Build** — implement until the capability evals pass.
3. **Analyze** — read 20–50 traces, open-code the failures, add new failure types as tasks.
4. **Gate** — promote passing capability evals into the regression suite CI runs on every change.

## Repo layout

```
case-resolution-evals/
  spec/            tasks/*.yaml, personas/, seeds/, rubrics/   (platform-neutral)
  adapters/        spec → harness formats (Inspect AI)
  open-stack/      agent/, mcp_servers/, kb/, evals/, stats/, tests/
  analysis/        error-analysis notebooks, pass^k reports, charts
  .github/workflows/ pr.yml (deterministic, no API keys)
  content/         blog drafts and video scripts, one folder per week
```

## Open-stack build

| Layer | Choice |
| --- | --- |
| Agent runtime | LangGraph (supervisor with triage / resolution / compliance sub-agents later); LiteLLM model client |
| Tools | FastMCP servers for orders, refunds and CRM over seeded SQLite |
| Agentic retrieval | Policy knowledge base in pgvector behind a search tool |
| Memory | LangGraph checkpointer (session) and store (cross-session) |
| Eval harness | Inspect AI tasks, pytest, Ragas, custom judges |
| CI gate | GitHub Actions: replayed PR tier, nightly live tier, pass^k gate |
| Tracing | OpenTelemetry GenAI conventions, Arize Phoenix |
| Red-teaming | Promptfoo, garak, AgentDojo-style injections |
| Cost routing | LiteLLM router, cost per resolved case |
| Human approval | LangGraph `interrupt()` for refunds over $500 |

## Quick start

```bash
cd open-stack
uv sync
uv run pytest                                              # deterministic checks
uv run python ../spec/seeds/generate_seeds.py              # regenerate synthetic seed data
```

## Ground rules

- **Synthetic data only.** No real customer records or names in the repo, traces or cassettes.
- **Pinned versions** via `open-stack/uv.lock` (LangGraph, FastMCP, MCP SDK, LiteLLM).
- **Secrets** live in GitHub environment secrets that fork PRs cannot read.
- **Budgets:** set a monthly model budget in LiteLLM; the nightly job stops when it is reached.

## License

MIT
