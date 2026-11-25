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
| `refunds` | `issue_refund(order_id, amount, reason, item_id=None)` |
| `crm` | `update_case(case_id, status)`, `add_case_note(case_id, body)` |

In v0 the tools only check that the data makes sense (the order exists, the item belongs to
it, the amount is positive). They do **not** enforce refund policy, on purpose: the evals
measure whether the agent follows policy, and deterministic guardrails come in week 14.

```bash
uv run python -m mcp_servers.db --out .data/cases.sqlite         # seeds -> SQLite
uv run python -m mcp_servers.orders --db .data/cases.sqlite      # stdio server (also refunds, crm)
```

Default model: `anthropic/claude-opus-5-5` via LiteLLM (override with `AGENT_MODEL`).
