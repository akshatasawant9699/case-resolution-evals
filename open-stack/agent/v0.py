"""Agent v0: one LangGraph agent, every MCP tool, a thin prompt, no policy checks.

v0 is the baseline the evals are expected to fail. It knows nothing about refund policy
beyond what the tool descriptions say, and the tools don't enforce policy either. Each failed
task becomes the reason for a later change.

The graph is a plain tool loop:

    START -> model -> (tool calls?) -> tools -> model -> ... -> END
"""

from __future__ import annotations

import json
import operator
import os
from contextlib import AsyncExitStack
from typing import Annotated, Any, Awaitable, Callable, TypedDict

from fastmcp import Client
from langgraph.graph import END, START, StateGraph

from mcp_servers import crm, orders, refunds
from mcp_servers.db import REFERENCE_DATE

DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "anthropic/claude-opus-5-5")
MAX_MODEL_CALLS_PER_TURN = 15

SYSTEM_PROMPT = """\
You are a customer support agent for an online home-goods store. Help the customer using the \
tools available. Today is {today}. The authenticated customer is {customer_id}. The open \
support case is {case_id}."""

# (messages, tools) -> (assistant message in OpenAI format, usage dict)
CompletionFn = Callable[[list[dict], list[dict]], Awaitable[tuple[dict, dict]]]


def litellm_completion(model: str = DEFAULT_MODEL, max_tokens: int = 4096) -> CompletionFn:
    """Call a model through LiteLLM. No temperature or forced tool_choice: Opus 5.5 rejects both."""
    import litellm

    async def complete(messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
        resp = await litellm.acompletion(model=model, messages=messages, tools=tools, max_tokens=max_tokens)
        msg = resp.choices[0].message
        assistant: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                for tc in msg.tool_calls
            ]
        try:
            cost = litellm.completion_cost(completion_response=resp)
        except Exception:  # unknown model price; cost is reporting only
            cost = 0.0
        usage = {"input_tokens": resp.usage.prompt_tokens, "output_tokens": resp.usage.completion_tokens,
                 "cost_usd": cost or 0.0}
        return assistant, usage

    return complete


class Toolbox:
    """Opens MCP clients for the orders, refunds and CRM servers and routes tool calls."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._stack = AsyncExitStack()
        self._route: dict[str, Client] = {}
        self.specs: list[dict] = []

    async def __aenter__(self) -> "Toolbox":
        for module in (orders, refunds, crm):
            client = await self._stack.enter_async_context(Client(module.build_server(self.db_path)))
            for tool in await client.list_tools():
                self._route[tool.name] = client
                self.specs.append({"type": "function", "function": {
                    "name": tool.name, "description": tool.description or "",
                    "parameters": tool.input_schema}})
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    async def call(self, name: str, args: dict) -> tuple[str, bool]:
        """Return (text result, is_error). Errors go back to the model rather than raising."""
        client = self._route.get(name)
        if client is None:
            return f"Unknown tool {name}.", True
        result = await client.call_tool(name, args, raise_on_error=False)
        if result.content and hasattr(result.content[0], "text"):
            text = result.content[0].text
        else:
            text = json.dumps(result.data, default=str)
        return text, bool(result.is_error)


class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    tool_calls: Annotated[list[dict], operator.add]
    usage: Annotated[list[dict], operator.add]


def build_graph(toolbox: Toolbox, complete: CompletionFn):
    async def model(state: AgentState) -> dict:
        assistant, usage = await complete(state["messages"], toolbox.specs)
        return {"messages": [assistant], "usage": [usage]}

    async def tools(state: AgentState) -> dict:
        results, log = [], []
        for tc in state["messages"][-1]["tool_calls"]:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args, (text, is_error) = {}, ("Arguments were not valid JSON.", True)
            else:
                text, is_error = await toolbox.call(name, args)
            results.append({"role": "tool", "tool_call_id": tc["id"], "content": text})
            log.append({"tool": name, "args": args, "is_error": is_error, "result": text})
        return {"messages": results, "tool_calls": log}

    def route(state: AgentState) -> str:
        return "tools" if state["messages"][-1].get("tool_calls") else END

    graph = StateGraph(AgentState)
    graph.add_node("model", model)
    graph.add_node("tools", tools)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", route, {"tools": "tools", END: END})
    graph.add_edge("tools", "model")
    return graph.compile()


async def run_conversation(db_path: str, customer_id: str, case_id: str, user_turns: list[str],
                           complete: CompletionFn | None = None) -> AgentState:
    """Play scripted customer turns against the agent and return the final state."""
    complete = complete or litellm_completion()
    state: AgentState = {
        "messages": [{"role": "system", "content": SYSTEM_PROMPT.format(
            today=REFERENCE_DATE, customer_id=customer_id, case_id=case_id)}],
        "tool_calls": [], "usage": [],
    }
    async with Toolbox(db_path) as toolbox:
        graph = build_graph(toolbox, complete)
        for turn in user_turns:
            state["messages"] = [*state["messages"], {"role": "user", "content": turn}]
            # No checkpointer, so each invoke starts empty and the reducers rebuild the state.
            state = await graph.ainvoke(state, {"recursion_limit": 2 * MAX_MODEL_CALLS_PER_TURN + 1})
    return state
