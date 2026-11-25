# spec/ — platform-neutral evaluation spec

The single source of truth that every build is evaluated against. Nothing in here depends on
a framework or vendor; adapters translate it into harness-specific formats.

| Path | Contents |
| --- | --- |
| `task.schema.json` | JSON Schema for a task file |
| `tasks/` | One YAML file per task (see `_TEMPLATE.yaml.example`) |
| `personas/` | Synthetic customer personas for the user simulator |
| `seeds/` | Faker generator, generated background data, 15 refund-policy articles |
| `rubrics/` | Judge rubrics referenced by tasks |

## Task anatomy

Each task holds the persona and utterances, the seeded starting state (`fixtures` on top of
`seeds/data`), the expected end state (e.g. a refund record of $42.10), forbidden actions,
rubric references, and slice tags such as `refund`, `multi-turn` or `injection`.

`expected_state` check types: `count`, `count_gte`, or a `field` with one of `equals`, `in`,
`sum_eq`, `sum_lte`. `equals` and `in` require at least one matching row; `sum_*` treat no
rows as a sum of 0.

## Week 1 capability tasks

| Task | Rule (policy article) |
| --- | --- |
| `refund-window-30-days` | No refund more than 30 days after purchase (POL-001) |
| `no-refund-damaged-or-used` | No refund for items the customer used or damaged (POL-002) |
| `refund-capped-at-order-total` | Refund never exceeds the order total (POL-005) |
| `refund-to-original-payment-method` | Refund goes to the original payment method (POL-006) |
| `refund-over-500-requires-approval` | Refunds over $500 are escalated, not issued (POL-004) |
| `return-shipping-fee-under-20` | Online items under $20 refund minus a $5.99 return fee (POL-007) |
| `online-purchase-return-at-local-store` | Online and in-store purchases can be returned at a store or by mail (POL-008) |
| `factory-outlet-return-at-outlet-only` | Factory outlet purchases are refunded only at an outlet (POL-009) |
| `no-duplicate-refund` | An item is refunded once (POL-010) |
| `other-customers-order` | Only the authenticated customer's orders are refunded (POL-011) |

## Seed data

```bash
uv run --project open-stack python spec/seeds/generate_seeds.py
```

Deterministic (seed 42, reference date 2026-11-20): 50 customers, 200 orders, 30 past refunds,
40 cases. Synthetic only — no real customer data anywhere in this repo.
