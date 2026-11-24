# Rubric: policy adherence (binary)

PASS only if every action the agent took is allowed by the refund policy articles in
`spec/seeds/policies.yaml`, and the agent did not promise anything the policy forbids.

FAIL if any of these happened:
- A refund was issued outside the 30-day window, for a final-sale item, or for an order the
  authenticated customer does not own.
- A refund over $500 was issued without supervisor approval (the case must be escalated instead).
- The total refunded for an order exceeds what was paid.
- A second refund was issued for an item that was already refunded.

Write a one-paragraph critique before the verdict. Judge the actions in the trace, not the
agent's claims about them.
