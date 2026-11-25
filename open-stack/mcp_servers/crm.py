"""CRM MCP server: support-case updates."""

from __future__ import annotations

from typing import Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from mcp_servers._cli import run
from mcp_servers.db import REFERENCE_DATE, connect, next_id, row_to_dict

CaseStatus = Literal["open", "pending", "escalated", "resolved"]


def build_server(db_path: str) -> FastMCP:
    mcp = FastMCP("crm")

    def _require_case(conn, case_id: str) -> None:
        if conn.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,)).fetchone() is None:
            raise ToolError(f"Case {case_id} not found.")

    @mcp.tool
    def update_case(case_id: str, status: CaseStatus) -> dict:
        """Set a support case's status.

        Use "escalated" when a supervisor must approve, "resolved" when the issue is handled,
        "pending" when waiting on the customer. Returns the updated case.
        """
        with connect(db_path) as conn:
            _require_case(conn, case_id)
            conn.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?",
                         (status, REFERENCE_DATE, case_id))
            return row_to_dict(conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone())

    @mcp.tool
    def add_case_note(case_id: str, body: str) -> dict:
        """Add an internal note to a support case recording what was done and why."""
        if not body.strip():
            raise ToolError("Note body must not be empty.")
        with connect(db_path) as conn:
            _require_case(conn, case_id)
            note_id = next_id(conn, "case_notes", "NOTE-A")
            conn.execute("INSERT INTO case_notes (id, case_id, body, created_at) VALUES (?, ?, ?, ?)",
                         (note_id, case_id, body.strip(), REFERENCE_DATE))
            conn.execute("UPDATE cases SET updated_at = ? WHERE id = ?", (REFERENCE_DATE, case_id))
            return row_to_dict(conn.execute("SELECT * FROM case_notes WHERE id = ?", (note_id,)).fetchone())

    return mcp


if __name__ == "__main__":
    run(build_server, "crm")
