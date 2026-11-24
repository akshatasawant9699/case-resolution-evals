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

Default model: `anthropic/claude-opus-5-5` via LiteLLM (override with `AGENT_MODEL`).
