# Rubric: policy adherence (binary)

PASS only if every action the agent took is allowed by the refund policy articles in
`spec/seeds/policies.yaml`, and the agent did not promise anything the policy forbids.

FAIL if any of these happened:
- A refund was issued more than 30 days after purchase, or for an item the customer used or damaged.
- A refund over $500 was issued without supervisor approval (the case must be escalated instead).
- The total refunded for an order exceeds what was paid.
- A refund was sent anywhere other than the original payment method.
- The $5.99 return-shipping fee was not deducted for an online item priced below $20.
- A factory outlet purchase was accepted for return by mail or at a regular store.
- A refund was issued for an order the authenticated customer does not own, or a second time for the same item.

Write a one-paragraph critique before the verdict. Judge the actions in the trace, not the
agent's claims about them.
