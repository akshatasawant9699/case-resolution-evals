"""Shared entry point so each server can run standalone over stdio."""

from __future__ import annotations

import argparse
import os
from typing import Callable

from fastmcp import FastMCP


def run(build_server: Callable[[str], FastMCP], name: str) -> None:
    parser = argparse.ArgumentParser(description=f"Run the {name} MCP server over stdio.")
    parser.add_argument("--db", default=os.environ.get("CASE_DB", ".data/cases.sqlite"),
                        help="SQLite path (build one with `python -m mcp_servers.db`)")
    build_server(parser.parse_args().db).run()
