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

PRODUCTS = [
    ("SKU-MUG", "Ceramic mug set", 42.10, False),
    ("SKU-LAMP", "Desk lamp", 64.00, False),
    ("SKU-KETTLE", "Electric kettle", 79.99, False),
    ("SKU-HDPH", "Wireless headphones", 129.00, False),
    ("SKU-CABLE", "USB-C cable", 15.00, False),
    ("SKU-CHAIR", "Office chair", 389.00, False),
    ("SKU-DESK", "Standing desk", 742.50, False),
    ("SKU-RUG", "Wool rug", 219.00, True),
    ("SKU-PLANT", "Faux plant", 24.99, True),
    ("SKU-BAG", "Laptop bag", 89.00, False),
]

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
        age = (REFERENCE_DATE - placed).days
        status = "processing" if age < 2 else "shipped" if age < 6 else rng.choice(["delivered"] * 9 + ["cancelled"])
        delivered = (placed + timedelta(days=rng.randint(3, 6))).isoformat() if status == "delivered" else None
        order_id = f"ORD-{i:05d}"
        shipping = rng.choice([0.0, 5.99, 9.99])
        subtotal = 0.0
        for sku, name, price, final_sale in rng.sample(PRODUCTS, rng.randint(1, 3)):
            item_n += 1
            qty = rng.choice([1, 1, 1, 2])
            subtotal += price * qty
            items.append(
                {"id": f"ITM-{item_n:06d}", "order_id": order_id, "sku": sku, "name": name,
                 "unit_price": price, "quantity": qty, "final_sale": final_sale}
            )
        orders.append(
            {"id": order_id, "customer_id": rng.choice(customers)["id"], "status": status,
             "placed_at": placed.isoformat(), "delivered_at": delivered,
             "shipping_fee": shipping, "total": round(subtotal + shipping, 2)}
        )

    delivered_orders = [o for o in orders if o["status"] == "delivered"]
    refunds = []
    for i, order in enumerate(rng.sample(delivered_orders, N_REFUNDS), start=1):
        item = rng.choice([it for it in items if it["order_id"] == order["id"]])
        refunds.append(
            {"id": f"REF-{i:04d}", "order_id": order["id"], "item_id": item["id"],
             "amount": item["unit_price"], "reason": rng.choice(["damaged", "defective", "wrong_item"]),
             "status": "completed", "created_at": order["delivered_at"], "created_by": "seed"}
        )

    cases = []
    for i, order in enumerate(rng.sample(orders, N_CASES), start=1):
        opened = (date.fromisoformat(order["placed_at"]) + timedelta(days=rng.randint(1, 10))).isoformat()
        cases.append(
            {"id": f"CASE-{i:04d}", "customer_id": order["customer_id"], "order_id": order["id"],
             "subject": rng.choice(["Where is my order?", "Item arrived damaged", "Refund request", "Wrong item"]),
             "status": rng.choice(["open", "resolved", "resolved"]), "created_at": opened, "updated_at": opened}
        )

    return {"customers": customers, "orders": orders, "order_items": items,
            "refunds": refunds, "cases": cases, "case_notes": []}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for table, rows in generate().items():
        (OUT / f"{table}.json").write_text(json.dumps(rows, indent=2) + "\n")
        print(f"{table}: {len(rows)} rows")


if __name__ == "__main__":
    main()
