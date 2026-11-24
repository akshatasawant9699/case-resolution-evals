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
`sum_eq`, `sum_lte`.

## Seed data

```bash
uv run --project open-stack python spec/seeds/generate_seeds.py
```

Deterministic (seed 42, reference date 2026-11-20): 50 customers, 200 orders, 30 past refunds,
40 cases. Synthetic only — no real customer data anywhere in this repo.
