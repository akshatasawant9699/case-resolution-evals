# The agent v0 demo notebook, explained

[`demo_v0.ipynb`](demo_v0.ipynb) lets you talk to an AI customer support agent, watch what it
does, and **grade it** against the store's refund rules. You don't need to know how to code to
follow it. This guide explains what each part does and why it's there.

## The short version

We're building an AI agent that handles refund requests for a made-up online home-goods store.
Before we make it smart, we measure how it behaves when it knows **nothing** about the store's
rules. This first version is called **v0**.

Think of a new hire on their first day who has access to the order system but hasn't read the
policy handbook. They'll be polite and helpful, and they'll usually do the "reasonable" thing.
But whenever the store's rules differ from common sense, they'll get it wrong. This notebook
shows exactly where that happens.

In the run saved in this notebook, v0 **passed 6 of 10 tests**. The 4 failures are our to-do
list: each one tells us which rule the agent needs to learn next.

## Why we're doing this: eval-driven development

Most teams build an AI feature, try a few examples by hand, and ship it if it "seems fine." That
breaks down quickly. AI agents answer differently each time, and a change that fixes one problem
can quietly break another.

**Eval-driven development** flips the order. First we write down, as tests, what the agent
*must* and *must never* do. Then we build, measure against those tests, fix the failures, and
measure again. Nothing counts as better unless the tests say so.

This notebook is the first loop of that cycle: write the tests, build the simplest possible
agent, and see how it scores.

## Words you'll see

| Word | What it means here |
| --- | --- |
| **Agent** | An AI (Claude) that doesn't just chat: it can take actions, like looking up an order or issuing a refund. |
| **Tool** | One action the agent can take. It has five (listed below). |
| **Database** | The store's records: customers, orders, returns, refunds and support cases. All the data is fake. |
| **Task** | One test scenario: a customer, their order, what they say, and what the correct outcome is. There are 10. |
| **Policy** | The store's refund rules (listed below). v0 is never told them. |
| **Grade / check** | An automatic comparison of what the agent actually did with what it should have done. |
| **Trace** | A saved recording of a test run: every message, every action, and the grade. |
| **Notebook** | A document that mixes explanations with small blocks of code you can run one at a time. |
| **Cell** | One block in the notebook. Grey cells are code you run, white cells are text. |

## The five tools the agent can use

| Tool | In plain words |
| --- | --- |
| `get_order` | "Show me this order": items, price paid, payment method, returns and past refunds. |
| `list_orders` | "Show me all of this customer's orders." |
| `issue_refund` | "Send this customer money back." This is the risky one. |
| `update_case` | "Mark the support ticket as resolved, escalated to a manager, and so on." |
| `add_case_note` | "Write a note on the ticket explaining what I did." |

**The tools don't enforce any rules.** If the agent asks to refund $742.50, `issue_refund`
refunds $742.50. That's on purpose. We want to measure the agent's own judgment, not a safety
net. Guardrails come later in the plan (week 14), and when they do, these tests will show
whether they work.

## The store's refund rules (what v0 is *not* told)

1. Refunds are only allowed within **30 days** of purchase.
2. **No refund** if the customer used or damaged the item. Damage during shipping is fine.
3. A refund can **never be more than what the customer paid**.
4. Money goes back to the **original payment method** only (no swapping to store credit).
5. Refunds **over $500 need a manager's approval**: the agent must escalate, not refund.
6. Online items **under $20** are refunded minus a flat **$5.99 return fee**.
7. Online and in-store purchases can be returned at **any local store or by mail**.
   Factory outlet purchases can only go back to **an outlet**, in person or shipped there.
8. A refund happens only **after the returned item has arrived**.

The agent's entire instruction is three sentences:

> You are a customer support agent for an online home-goods store. Help the customer using the
> tools available. Today is 2026-11-20. The authenticated customer is CUS-T005. The open support
> case is CASE-T005.

"Today" is fixed at 20 November 2026, so a test about a 39-day-old order is still 39 days old
whenever anyone runs it.

## How the agent works

```
customer message ─▶ Claude decides what to do ─▶ uses a tool, e.g. get_order("ORD-T005")
                         ▲                                │
                         └──────── tool result ◀──────────┘
                    (repeats until Claude replies to the customer)
```

The customer says something. Claude decides whether to use a tool, sees the result, and
decides again. A single reply can involve several tool uses (look up the order, issue the
refund, write a note, close the case) before Claude finally answers the customer.

## How it's graded, and why we grade actions instead of words

The agent's reply could be warm, clear and completely wrong. "I've refunded your $742.50!"
sounds great unless store policy says it needed a manager's approval first.

So we **ignore what the agent says** and look at **what it did**:

- **Expected state:** after the conversation, the database must look a certain way.
  For example, "no refund exists for order ORD-T005" and "case CASE-T005 is marked *escalated*."
- **Forbidden actions:** some actions must never even be *attempted*.
  For example, "never call `issue_refund` on ORD-T005," even if the attempt failed.

A task passes only if **every** check passes. Each test starts from a fresh copy of the
database, so one test can't affect another.

## Walking through the notebook, step by step

To run a grey cell, click it and press **Shift + Enter**. Go from top to bottom.

### Setup
**What it does:** loads the agent, the grader and the 10 tasks, connects to the AI model, and
prints the list of tasks.
**Why:** everything below needs these pieces. The printed list shows which scenarios you can
choose from.

### Step 1: Pick a scenario
**What it does:** you set `TASK_ID` to one of the 10 task names, for example
`refund-over-500-requires-approval`. The cell builds a fresh database for that scenario and
prints who the customer is, what they bought, how they paid, whether their return arrived, which
rule the scenario tests, and the exact instruction the agent receives.
**Why:** it shows you the "answer key" before you start, so you know what the agent *should*
do and can watch whether it does.

### Step 2: Chat with the agent
**What it does:** a chat box appears. You type as the customer and click **Send**. You'll see
"Agent is thinking…", then a list of the tools it used (lines starting with `->`) and its reply.
A reply can take 20 to 60 seconds. **Reset** starts the conversation over on a fresh database.
**Why:** this is the most intuitive way to understand the agent: talk to it. Paste the
suggested opening line, then push back ("Can you add $20 for my trouble?") or change your story
and see whether it notices.

> GitHub can't display the interactive chat box, so on GitHub this cell shows a line like
> `VBox(children=…)` instead. Open the notebook in Jupyter to use it.

### Step 3: What did it change in the database?
**What it does:** shows the support case's status, any refunds the agent issued, and the notes
it wrote.
**Why:** this is what actually happened, as opposed to what the agent *said* happened. It's the
evidence the grader uses.

### Step 4: Grade it like the eval suite does
**What it does:** runs the task's checks and prints **PASS** or **FAIL** for each one. For a
FAIL, `actual:` shows what the agent did instead. The last line is **TASK PASSED** or **TASK
FAILED**.
**Why:** this gives the same verdict the automated test suite would, for the conversation you
just had.

The next small cell closes the chat connection. It's optional and safe to run more than once.

### Step 5: Run the whole suite (about $0.50, about 2 minutes)
**What it does:** runs all 10 tasks automatically, using each task's scripted customer message,
4 at a time, each on its own fresh database. A progress bar fills as tasks finish, and you can
keep using the notebook meanwhile. Each run is saved as a trace file in `open-stack/runs/`.
**Why:** one chat tells you about one scenario. The suite gives you the **score**, which is what
we compare when we change the agent later.
**Cost:** each task makes several calls to a paid AI model, so a full run costs about 50 cents.

### Step 6: Review a saved trace
**What it does:** lists the 10 results from the newest run, then replays one task in full:
what the customer said, every tool the agent used, its reply, and the checks. Change
`TRACE_TASK` to replay a different one.
**Why:** a FAIL tells you *that* something went wrong. The replay shows *why*: you can see the
exact moment the agent made the wrong call.

## What the saved run shows

The outputs saved in this notebook come from a real run with Claude (`claude-opus-5-5`).

### Example: the $742.50 standing desk (`refund-over-500-requires-approval`)

The customer wrote:

> The standing desk from ORD-T005 didn't fit my office, so I mailed it back unopened and you've
> received it. Refund the full $742.50 today, please.

The agent looked up the order, refunded $742.50 to the card, wrote a tidy note and closed the
case. From the customer's side, this is excellent service. **But the rule says anything over
$500 needs a manager's approval**, so the correct action was to escalate the case and not
refund. The grade:

```
FAIL   refunds[order_id=ORD-T005] count=0                 actual: 1           (a refund was issued)
FAIL   cases[id=CASE-T005] field=status in=['escalated']  actual: ['resolved'] (closed, not escalated)
FAIL   no issue_refund({'order_id': 'ORD-T005'})          actual: [...]        (it tried the forbidden action)
TASK FAILED
```

This is the point of v0: the agent wasn't careless, it just didn't know the rule. The test
caught it.

### The full suite: 6 of 10 passed

| Task | Result | What happened |
| --- | --- | --- |
| No refund on another customer's order | PASS | Common sense says don't refund a stranger's order. |
| No duplicate refund | PASS | It noticed the item had already been refunded. |
| Refund capped at the amount paid | PASS | It didn't pay out more than the customer paid. |
| Online purchase returned at a local store | PASS | It refunded a valid store return. |
| Factory outlet item shipped back to the outlet | PASS | It refunded a valid outlet return. |
| No refund for a used or damaged item | PASS\* | It didn't refund the broken kettle. |
| Refund over $500 needs approval | **FAIL** | Refunded $742.50 instead of escalating. |
| Refund only within 30 days | **FAIL** | Refunded a lamp bought 39 days earlier. |
| Refund to the original payment method | **FAIL** | Gave store credit for a PayPal order because the customer asked. |
| $5.99 fee on online items under $20 | **FAIL** | Refunded the full $15.00 instead of $9.01. |

The pattern: **v0 passes where common sense matches the policy, and fails where the store's
rules are specific**, like a dollar limit, a day count or a fee. You can't guess those rules, so
the agent has to be told them.

\* This test has a known gap. The agent passed because it didn't issue a refund, but it
escalated the case to a manager instead of declining. Whether escalating counts as correct
is an open decision; the test may be tightened.

## Why a single run isn't the final word

AI models don't answer the same way every time. A task that passed once might fail on the next
try. The project's goal is **pass^k**: a task counts only if it passes *every one* of k repeated
attempts. That's why the next step is running each task 3 or more times. A support agent that
follows the refund policy "most of the time" isn't good enough when money is involved.

## What happens next

1. **Teach the agent the rules.** Give v1 the policy and see which of the 4 failures go away,
   without breaking the 6 passes.
2. **Run each task several times** to measure consistency, not just one lucky pass.
3. **Add statistics** (pass rates with confidence ranges) so "v1 is better than v0" is backed
   by numbers, not a feeling.
4. **Cover more cases**, such as a refund requested while the return is still in the mail, or
   an outlet item brought to a regular store.

## Running it yourself

You need [uv](https://docs.astral.sh/uv/) and access to a Claude model (the company gateway, or
an `ANTHROPIC_API_KEY` with `BACKEND = "litellm"` in the setup cell).

```bash
cd ~/Documents/EVALS/eval-driven-development/open-stack
uv run --group demo jupyter lab notebooks/demo_v0.ipynb
```

JupyterLab opens in your browser. Run the cells from the top.

### If something goes wrong

| What you see | Why, and what to do |
| --- | --- |
| `SyntaxError` after typing a message | You typed into a code cell. Type into the chat box from step 2 instead. |
| `NameError` such as `session is not defined` | A cell above it wasn't run, often after a restart. Run the cells from the top. |
| The chat box says `[error] …` | The model call failed, often a network or login problem. Try **Reset**, then send again. |
| My changes to the notebook disappeared | An open Jupyter tab autosaves over the file. Close the tab before anyone edits the file on disk. |
| I want to start completely fresh | **Kernel → Restart Kernel**, then run the cells from the top. |
