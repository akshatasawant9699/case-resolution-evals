# Rubric: action correctness (binary)

PASS only if the agent took the actions the customer's situation required, with correct
arguments, and nothing else:
- Correct tool for the request (lookup vs. refund vs. case update).
- Correct order, item and amount.
- Case left in a state that matches what happened (note added, status updated).

FAIL on a wrong tool, wrong argument, a missing required action, or an unrequested side effect.
Write a one-paragraph critique before the verdict.
