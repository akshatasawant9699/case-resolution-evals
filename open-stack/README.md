# open-stack/ — generic (framework-based) build

| Path | Purpose |
| --- | --- |
| `agent/` | LangGraph agent (v0: one agent, all tools, thin prompt) with a LiteLLM model client |
| `mcp_servers/` | FastMCP servers over seeded SQLite: `orders`, `refunds`, `crm` |
| `kb/` | Policy knowledge base (pgvector) for agentic retrieval |
| `evals/` | Task runner, state checks, trace capture (JSONL) |
| `stats/` | pass@k, pass^k, Wilson intervals, paired comparisons |
| `tests/` | Deterministic tests (run in CI on every PR, no API keys) |

```bash
cd open-stack
uv sync
uv run pytest
```

## MCP servers

| Server | Tools |
| --- | --- |
| `orders` | `get_order(order_id)`, `list_orders(customer_id)` |
| `refunds` | `issue_refund(order_id, amount, reason, refund_method, return_channel, item_id=None)` |
| `crm` | `update_case(case_id, status)`, `add_case_note(case_id, body)` |

In v0 the tools only check that the data makes sense (the order exists, the item belongs to
it, the amount is positive). They do **not** enforce refund policy, on purpose: the evals
measure whether the agent follows policy, and deterministic guardrails come in week 14.

```bash
uv run python -m mcp_servers.db --out .data/cases.sqlite         # seeds -> SQLite
uv run python -m mcp_servers.orders --db .data/cases.sqlite      # stdio server (also refunds, crm)
```

## Agent v0 and the eval run

`agent/v0.py` is a LangGraph tool loop (model -> tools -> model) with all five MCP tools and a
three-sentence prompt (today's date, the customer ID, the case ID). It has no policy knowledge
and no checks, so it is expected to fail several tasks; each failure drives a later change.

```bash
export ANTHROPIC_API_KEY=...
uv run python -m evals.run                    # each task once -> runs/v0-<timestamp>.jsonl
uv run python -m evals.run --trials 3 --task no-duplicate-refund

# Or reuse Claude Code's Bedrock gateway (no separate key; see agent/gateway.py)
uv run python -m evals.run --backend gateway
```

### Try it yourself

```bash
# Terminal chat: a task's scenario, or any seeded customer. /state shows what changed.
uv run python -m agent.chat --task refund-over-500-requires-approval
uv run python -m agent.chat --customer CUS-0001

# Demo notebook: pick a scenario, chat, inspect the database, grade, review traces
uv run --group demo jupyter lab notebooks/demo_v0.ipynb
```

New to the notebook? [notebooks/README.md](notebooks/README.md) explains every step in plain
language, with the results of a real run.

Both use the gateway by default; pass `--backend litellm` (chat) or set `BACKEND = "litellm"`
(notebook) to use `ANTHROPIC_API_KEY` instead.

Each trial gets a fresh database (seeds plus task fixtures), plays the task's conversation,
then checks `expected_state` and `forbidden_actions`. A JSONL line holds the task id, pass/fail,
every check with its actual value, the tool calls, the full message history, and token usage
and cost. `runs/` is git-ignored.

Default model: `anthropic/claude-opus-5-5` via LiteLLM (override with `--model` or `AGENT_MODEL`).
