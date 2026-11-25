"""Exercise the three MCP servers through the real MCP protocol (in-memory transport)."""

import json
import sqlite3

import pytest
from fastmcp import Client

from mcp_servers import crm, orders, refunds
from mcp_servers.db import REFERENCE_DATE, SEED_DIR, build_database

FIXTURES = {
    "customers": [{"id": "CUS-X1", "name": "Test Person", "email": "t@example.com",
                   "tier": "standard", "created_at": "2025-01-01"}],
    "orders": [{"id": "ORD-X1", "customer_id": "CUS-X1", "status": "delivered", "placed_at": "2026-11-10",
                "delivered_at": "2026-11-14", "shipping_fee": 5.99, "total": 50.99}],
    "order_items": [{"id": "ITM-X1", "order_id": "ORD-X1", "sku": "SKU-CABLE", "name": "USB-C cable",
                     "unit_price": 15.00, "quantity": 3, "final_sale": False}],
    "cases": [{"id": "CASE-X1", "customer_id": "CUS-X1", "order_id": "ORD-X1", "subject": "Refund request",
               "status": "open", "created_at": "2026-11-19", "updated_at": "2026-11-19"}],
}


@pytest.fixture
def db(tmp_path):
    return str(build_database(tmp_path / "t.sqlite", FIXTURES))


def query(db, sql, *args):
    with sqlite3.connect(db) as conn:
        return conn.execute(sql, args).fetchall()


async def call(server, tool, args):
    async with Client(server) as client:
        return await client.call_tool(tool, args, raise_on_error=False)


def test_reference_date_matches_seed_generator():
    import importlib.util
    spec = importlib.util.spec_from_file_location("g", SEED_DIR.parent / "generate_seeds.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.REFERENCE_DATE.isoformat() == REFERENCE_DATE


def test_database_loads_seeds_and_fixtures(db):
    assert query(db, "SELECT COUNT(*) FROM customers")[0][0] == 51
    assert query(db, "SELECT COUNT(*) FROM orders")[0][0] == 201
    assert query(db, "SELECT COUNT(*) FROM refunds")[0][0] == 30


@pytest.mark.parametrize("module, expected", [
    (orders, {"get_order", "list_orders"}),
    (refunds, {"issue_refund"}),
    (crm, {"update_case", "add_case_note"}),
])
async def test_tool_lists(db, module, expected):
    async with Client(module.build_server(db)) as client:
        tools = await client.list_tools()
    assert {t.name for t in tools} == expected
    assert all(t.description for t in tools)


async def test_get_order_includes_items_and_refunds(db):
    result = await call(orders.build_server(db), "get_order", {"order_id": "ORD-X1"})
    assert not result.is_error
    assert result.data["customer_id"] == "CUS-X1"
    assert result.data["items"][0]["final_sale"] is False
    assert result.data["refunds"] == []


async def test_get_order_unknown_id_is_an_error(db):
    result = await call(orders.build_server(db), "get_order", {"order_id": "ORD-NOPE"})
    assert result.is_error
    assert "not found" in result.content[0].text


async def test_list_orders(db):
    result = await call(orders.build_server(db), "list_orders", {"customer_id": "CUS-X1"})
    assert [o["id"] for o in json.loads(result.content[0].text)] == ["ORD-X1"]
    assert (await call(orders.build_server(db), "list_orders", {"customer_id": "CUS-NOPE"})).is_error


async def test_issue_refund_writes_record(db):
    result = await call(refunds.build_server(db), "issue_refund",
                        {"order_id": "ORD-X1", "amount": 15.0, "reason": "defective", "item_id": "ITM-X1"})
    assert not result.is_error
    assert result.data["id"] == "REF-A0001"
    assert query(db, "SELECT amount, created_by, status FROM refunds WHERE order_id = 'ORD-X1'") == [
        (15.0, "agent", "pending")]


@pytest.mark.parametrize("args, message", [
    ({"order_id": "ORD-NOPE", "amount": 10.0, "reason": "damaged"}, "not found"),
    ({"order_id": "ORD-X1", "amount": 0, "reason": "damaged"}, "greater than zero"),
    ({"order_id": "ORD-X1", "amount": 10.0, "reason": "damaged", "item_id": "ITM-000001"}, "not part of"),
])
async def test_issue_refund_integrity_errors(db, args, message):
    result = await call(refunds.build_server(db), "issue_refund", args)
    assert result.is_error and message in result.content[0].text
    assert query(db, "SELECT COUNT(*) FROM refunds WHERE created_by = 'agent'")[0][0] == 0


async def test_issue_refund_does_not_enforce_policy_in_v0(db):
    """Over-total refunds go through on purpose: policy is the agent's job until week 14."""
    result = await call(refunds.build_server(db), "issue_refund",
                        {"order_id": "ORD-X1", "amount": 999.0, "reason": "goodwill"})
    assert not result.is_error


async def test_update_case_and_add_note(db):
    server = crm.build_server(db)
    updated = await call(server, "update_case", {"case_id": "CASE-X1", "status": "escalated"})
    assert updated.data["status"] == "escalated"
    note = await call(server, "add_case_note", {"case_id": "CASE-X1", "body": "Needs approval."})
    assert note.data["id"] == "NOTE-A0001"
    assert query(db, "SELECT status FROM cases WHERE id = 'CASE-X1'") == [("escalated",)]


async def test_crm_rejects_bad_input(db):
    server = crm.build_server(db)
    assert (await call(server, "update_case", {"case_id": "CASE-X1", "status": "closed"})).is_error
    assert (await call(server, "update_case", {"case_id": "CASE-NOPE", "status": "open"})).is_error
    assert (await call(server, "add_case_note", {"case_id": "CASE-X1", "body": "  "})).is_error
