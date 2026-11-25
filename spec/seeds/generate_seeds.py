"""Generate the synthetic background dataset with Faker.

Deterministic: the same seed always produces byte-identical JSON, so the committed files in
spec/seeds/data/ can be regenerated and diffed. No real customer data is used anywhere.

    uv run --project open-stack python spec/seeds/generate_seeds.py
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

SEED = 42
REFERENCE_DATE = date(2026, 11, 20)  # "today" for every eval run
N_CUSTOMERS, N_ORDERS, N_REFUNDS, N_CASES = 50, 200, 30, 40
N_RETURNS_IN_TRANSIT = 10

PRODUCTS = [
    ("SKU-MUG", "Ceramic mug set", 42.10),
    ("SKU-LAMP", "Desk lamp", 64.00),
    ("SKU-KETTLE", "Electric kettle", 79.99),
    ("SKU-HDPH", "Wireless headphones", 129.00),
    ("SKU-CABLE", "USB-C cable", 15.00),
    ("SKU-CHAIR", "Office chair", 389.00),
    ("SKU-DESK", "Standing desk", 742.50),
    ("SKU-RUG", "Wool rug", 219.00),
    ("SKU-PLANT", "Faux plant", 24.99),
    ("SKU-SOCKS", "Wool socks", 12.50),
]
CHANNELS = ["online"] * 7 + ["in_store"] * 2 + ["factory_outlet"]
PAYMENT_METHODS = ["card", "card", "paypal", "gift_card"]

OUT = Path(__file__).parent / "data"


def generate() -> dict[str, list[dict]]:
    fake = Faker("en_US")
    Faker.seed(SEED)
    rng = random.Random(SEED)

    customers = [
        {
            "id": f"CUS-{i:04d}",
            "name": fake.name(),
            "email": fake.unique.safe_email(),
            "tier": rng.choice(["standard", "standard", "standard", "premium"]),
            "created_at": (REFERENCE_DATE - timedelta(days=rng.randint(30, 900))).isoformat(),
        }
        for i in range(1, N_CUSTOMERS + 1)
    ]

    orders, items = [], []
    item_n = 0
    for i in range(1, N_ORDERS + 1):
        placed = REFERENCE_DATE - timedelta(days=rng.randint(1, 120))
        channel = rng.choice(CHANNELS)
        if channel == "online":
            age = (REFERENCE_DATE - placed).days
            status = "processing" if age < 2 else "shipped" if age < 6 else rng.choice(["delivered"] * 9 + ["cancelled"])
            delivered = (placed + timedelta(days=rng.randint(3, 6))).isoformat() if status == "delivered" else None
            shipping = rng.choice([0.0, 5.99, 9.99])
        else:  # bought in person: handed over at purchase
            status, delivered, shipping = "delivered", placed.isoformat(), 0.0
        order_id = f"ORD-{i:05d}"
        subtotal = 0.0
        for sku, name, price in rng.sample(PRODUCTS, rng.randint(1, 3)):
            item_n += 1
            qty = rng.choice([1, 1, 1, 2])
            subtotal += price * qty
            items.append(
                {"id": f"ITM-{item_n:06d}", "order_id": order_id, "sku": sku, "name": name,
                 "unit_price": price, "quantity": qty}
            )
        orders.append(
            {"id": order_id, "customer_id": rng.choice(customers)["id"], "channel": channel,
             "payment_method": rng.choice(PAYMENT_METHODS), "status": status,
             "placed_at": placed.isoformat(), "delivered_at": delivered,
             "shipping_fee": shipping, "total": round(subtotal + shipping, 2)}
        )

    channel_for = {"online": "mail", "in_store": "store", "factory_outlet": "factory_outlet"}
    delivered_orders = [o for o in orders if o["status"] == "delivered"]
    sampled = rng.sample(delivered_orders, N_REFUNDS + N_RETURNS_IN_TRANSIT)
    refunds, returns = [], []
    for i, order in enumerate(sampled[:N_REFUNDS], start=1):
        item = rng.choice([it for it in items if it["order_id"] == order["id"]])
        returns.append(
            {"id": f"RET-{i:04d}", "order_id": order["id"], "item_id": item["id"],
             "channel": channel_for[order["channel"]], "status": "received",
             "received_at": order["delivered_at"]}
        )
        refunds.append(
            {"id": f"REF-{i:04d}", "order_id": order["id"], "item_id": item["id"],
             "amount": item["unit_price"], "reason": rng.choice(["changed_mind", "damaged_in_transit", "wrong_item"]),
             "refund_method": order["payment_method"],
             "return_channel": channel_for[order["channel"]],
             "status": "completed", "created_at": order["delivered_at"], "created_by": "seed"}
        )

    for i, order in enumerate(sampled[N_REFUNDS:], start=N_REFUNDS + 1):
        item = rng.choice([it for it in items if it["order_id"] == order["id"]])
        returns.append(
            {"id": f"RET-{i:04d}", "order_id": order["id"], "item_id": item["id"],
             "channel": channel_for[order["channel"]], "status": "in_transit", "received_at": None}
        )

    cases = []
    for i, order in enumerate(rng.sample(orders, N_CASES), start=1):
        opened = (date.fromisoformat(order["placed_at"]) + timedelta(days=rng.randint(1, 10))).isoformat()
        cases.append(
            {"id": f"CASE-{i:04d}", "customer_id": order["customer_id"], "order_id": order["id"],
             "subject": rng.choice(["Where is my order?", "Item arrived damaged", "Refund request", "Wrong item"]),
             "status": rng.choice(["open", "resolved", "resolved"]), "created_at": opened, "updated_at": opened}
        )

    return {"customers": customers, "orders": orders, "order_items": items, "returns": returns,
            "refunds": refunds, "cases": cases, "case_notes": []}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for table, rows in generate().items():
        (OUT / f"{table}.json").write_text(json.dumps(rows, indent=2) + "\n")
        print(f"{table}: {len(rows)} rows")


if __name__ == "__main__":
    main()
