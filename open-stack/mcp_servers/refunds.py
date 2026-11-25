"""Refunds MCP server: issues refunds.

v0 checks only data integrity (the order exists, the item belongs to it, the amount is
positive). It does NOT enforce refund policy: no window, cap, approval threshold, duplicate or
ownership checks. That is deliberate; the evals measure whether the agent follows policy, and
deterministic guardrails are added in week 14.
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from mcp_servers._cli import run
from mcp_servers.db import REFERENCE_DATE, connect, next_id, row_to_dict


def build_server(db_path: str) -> FastMCP:
    mcp = FastMCP("refunds")

    @mcp.tool
    def issue_refund(order_id: str, amount: float, reason: str, item_id: str | None = None) -> dict:
        """Issue a refund to the customer's original payment method.

        Args:
            order_id: The order to refund.
            amount: Refund amount in USD.
            reason: Short reason, e.g. damaged, defective, wrong_item.
            item_id: The line item being refunded, if the refund is for one item.

        Returns the created refund record. Refunds take 5 to 7 business days to arrive.
        """
        if amount <= 0:
            raise ToolError("Refund amount must be greater than zero.")
        with connect(db_path) as conn:
            if conn.execute("SELECT 1 FROM orders WHERE id = ?", (order_id,)).fetchone() is None:
                raise ToolError(f"Order {order_id} not found.")
            if item_id is not None and conn.execute(
                "SELECT 1 FROM order_items WHERE id = ? AND order_id = ?", (item_id, order_id)
            ).fetchone() is None:
                raise ToolError(f"Item {item_id} is not part of order {order_id}.")
            refund_id = next_id(conn, "refunds", "REF-A")
            conn.execute(
                "INSERT INTO refunds (id, order_id, item_id, amount, reason, status, created_at, created_by) "
                "VALUES (?, ?, ?, ?, ?, 'pending', ?, 'agent')",
                (refund_id, order_id, item_id, round(amount, 2), reason, REFERENCE_DATE),
            )
            return row_to_dict(conn.execute("SELECT * FROM refunds WHERE id = ?", (refund_id,)).fetchone())

    return mcp


if __name__ == "__main__":
    run(build_server, "refunds")
