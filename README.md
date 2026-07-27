# FLCS — Fraud, Loan, Compliance & Support

A multi-agent banking assistant. One chat box, four specialist agents, each with its
own tools and its own rulebook, coordinated by an orchestrator that decides who should
answer.

Built on the Claude API and the Model Context Protocol (MCP), deployed to AWS with
Terraform.

---

## What it does

Type a question in plain English. Depending on what you ask, it will:

- scan a day of card transactions and find the suspicious ones
- assess a loan application against affordability rules
- run KYC and sanctions checks across pending card applications
- answer "what is our policy on…" from the bank's own policy documents
- combine several of those in one answer when the question needs it

It opens real tickets in ServiceNow when a fraud case is confirmed.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser — static/index.html                                     │
└────────────────────────────┬─────────────────────────────────────┘
                             │  POST /ask   { question, session_id }
┌────────────────────────────▼─────────────────────────────────────┐
│  FastAPI — app.py                                                │
│  Holds each session's conversation history in memory             │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│  ORCHESTRATOR — agents/orchestrator.py                           │
│  Its tools ARE the other agents. Claude reads the question,      │
│  picks one or more, and writes each a self-contained brief.      │
│  Chosen agents run in parallel.                                  │
└──┬──────────────┬──────────────────┬──────────────────┬──────────┘
   │              │                  │                  │
┌──▼─────────┐ ┌──▼─────────┐ ┌──────▼───────┐ ┌────────▼─────────┐
│   FRAUD    │ │    LOAN    │ │  COMPLIANCE  │ │     SUPPORT      │
│   agent    │ │   agent    │ │    agent     │ │      agent       │
└──┬─────────┘ └──┬─────────┘ └──────┬───────┘ └────────┬─────────┘
   │ stdio        │ stdio            │ stdio            │ stdio
┌──▼─────────┐ ┌──▼─────────┐ ┌──────▼───────┐ ┌────────▼─────────┐
│   fraud_   │ │   loan_    │ │  compliance_ │ │    support_      │
│  tools.py  │ │  tools.py  │ │   tools.py   │ │    tools.py      │
│            │ │            │ │              │ │                  │
│  MCP       │ │  MCP       │ │  MCP         │ │  MCP             │
│  server    │ │  server    │ │  server      │ │  server          │
└──┬─────────┘ └──┬─────────┘ └──────┬───────┘ └────────┬─────────┘
   │              │                  │                  │
   ▼              ▼                  ▼                  ▼
transactions    loans           kyc.json          (policy only)
customers   affordability      sanctions
   │            ratios
   │
   └──► ServiceNow REST API        all four also expose search_policy
        (creates incidents)         over the shared policy index
                                              │
                                              ▼
                                    rag/policy_index.py
                                    data/policy_index.json
```

Two nested loops. The orchestrator's tools are agents; each agent's tools are its own
MCP server. The same `while` loop drives both levels — only the tool list differs.

---

## The common flow

Every question, whichever agent handles it, follows the same six steps.

1. The browser posts your question to `/ask`, along with a session id.
2. `app.py` looks up that session's previous turns and hands everything to the
   orchestrator.
3. The orchestrator sends Claude its system prompt, the list of available agents, and
   the conversation. Claude replies naming which agent or agents to use, and writes
   each one a self-contained instruction — the specialists cannot see your chat, so
   every customer id and amount has to be restated.
4. The chosen agent starts its MCP server as a subprocess, asks it what tools it has,
   and sends those tool descriptions to Claude along with the instruction. Claude
   picks a tool. The agent runs it. The result goes back to Claude. That repeats until
   Claude stops asking for tools and writes an answer.
5. The agent's answer returns to the orchestrator as a tool result.
6. The orchestrator sends everything to Claude one last time, which writes the final
   reply. That goes back to your browser and into the session history.

Nothing in the code decides which agent runs or which tool to call. Both are Claude's
decisions, made from the descriptions.

---

## Scenario 1 — fraud scan

**You ask:** *"Scan the latest day and give me the 1 most suspicious transaction."*

The orchestrator picks the fraud agent. The fraud agent calls `scan_day` on the fraud
MCP server.

`scan_day` is plain Python, not a language model. It scores every transaction that day
against the customer's own ninety-day average, the hour it was booked, whether the
city is new for that customer, the absolute value, and how many transactions that
customer made the same day. It returns only the top few, with the reasons each was
flagged.

That split is the point. A real bank processes hundreds of thousands of card
transactions a night. Putting them in front of a language model would cost a fortune
and overflow its context window. The scoring stays in code; the model only ever sees
the shortlist.

Claude then reads those few, calls `get_transaction` and `get_customer_transactions`
to check them against the customer's normal behaviour, and explains its judgement. It
asks before opening a ticket — it will not file one on its own.

**You reply:** *"yes"*

Because the session history is kept, Claude knows what it offered. It calls
`create_fraud_case`, which posts to the ServiceNow REST API and returns a real
incident number.

---

## Scenario 2 — loan assessment

**You ask:** *"List all pending loan applications."*

The orchestrator picks the loan agent, which calls `list_pending_applications`.

The MCP server calculates the affordability ratios — loan to income, repayment to
income, assets to loan — before returning anything. The model judges the numbers; it
never does the arithmetic. Two analysts should not get different ratios for the same
application, and a language model doing division is a source of quiet error.

Claude formats the result and offers to assess any one of them in depth.

---

## Scenario 3 — compliance scan

**You ask:** *"Run a compliance scan across pending card applications."*

The orchestrator picks the compliance agent, which calls `run_compliance_scan`.

That tool walks every pending application in Python, pulls the KYC record where one
exists, checks the identity document expiry, the address verification and the risk
rating, then screens the applicant's name against the sanctions list using fuzzy
matching. It returns the exceptions and the totals, not the whole set.

Fuzzy matching matters: sanctioned parties vary spelling and word order on purpose, so
exact matching alone would miss most real hits. The cost is a stream of false
positives, which is exactly what happens in real screening. The agent is instructed to
report a match as something requiring verification, never as a conclusion.

---

## Scenario 4 — support and policy

**You ask:** *"What is our policy on disputed transactions?"*

The orchestrator picks the support agent, which calls `search_policy`.

This is the retrieval step. The four policy documents were split into 113 paragraphs
ahead of time, each turned into a vector by a small local model, and saved to
`data/policy_index.json`. At request time only your question is turned into a vector,
and the closest few paragraphs come back.

Claude answers from those paragraphs and cites the document and section. If the search
returns nothing relevant it says the policy does not appear to cover it and recommends
escalation, rather than inventing an answer — which is the whole reason for grounding
it in retrieved text instead of the model's general knowledge of banking.

---

## Scenario 5 — several agents at once

**You ask:** *"C005 has a pending loan for $290,000. Check their fraud history as
well, then tell me whether to approve."*

This is the one that needs the orchestrator. It is not a fraud question or a loan
question; it is both.

Claude returns two tool calls in a single reply, one per agent, each with its own
brief. The two agents run **in parallel** — they share nothing, so there is no reason
to wait for one before starting the other.

The fraud agent reports the customer's transaction history and any suspicious pattern.
The loan agent reports the credit score, the affordability ratios and any earlier
declined application. Both answers return to the orchestrator, which sends them to
Claude together, and Claude weighs one against the other to produce a single
recommendation.

No code anywhere decides how to trade a fraud finding off against a credit score.

---

## Data

| File | Source |
|---|---|
| `data/transactions.json` | Kaggle credit-card fraud dataset (Sparkov) — 8 customers, 285 transactions |
| `data/customers.json` | same dataset |
| `data/labels.json` | ground-truth fraud labels, held back so the agent cannot cheat |
| `data/loans.json` | Kaggle loan approval dataset, mapped onto the same 8 customers |
| `data/card_applications.json` | Kaggle credit-card application dataset, 50 rows |
| `data/kyc.json` | generated — no public KYC dataset exists, it is all personal data |
| `data/sanctions.json` | real OFAC sanctions list, sampled to 99 entries |
| `data/policies/*.md` | four policy documents written for this project |
| `data/policy_index.json` | those documents chunked and embedded |

**One deliberate plant.** The customers are synthetic, so no genuine sanctions match
could ever occur. One entry matching customer C003 is added to the sanctions file and
marked `DEMO-PLANTED (not real OFAC data)` so the screening demo has something to
find.

---

## Running it locally

Set up the environment:

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-key
SERVICENOW_URL=https://your-instance.service-now.com
SERVICENOW_USER=admin
SERVICENOW_PASSWORD=your-password
```

Build the data files. This needs the raw Kaggle CSVs in `data/raw/` — they are
gitignored, so download them from Kaggle first:

```bash
venv/bin/python scripts/prep_data.py
venv/bin/python scripts/prep_loans.py
venv/bin/python scripts/prep_compliance.py
venv/bin/python scripts/prep_cards.py
venv/bin/python scripts/build_policy_index.py
```

Start it:

```bash
venv/bin/uvicorn app:app --reload
```

Open http://127.0.0.1:8000

---

## Deploying

Terraform builds everything: a keypair, a security group, and one t3.micro that
installs Docker on boot, clones this repo, builds the image and runs it.

Put your keys in `infra/terraform.tfvars` first — it is gitignored.

```bash
cd infra
terraform init
terraform apply
```

The public URL is printed as `app_url` when it finishes.

`terraform destroy` removes all of it. Do that when you are not demoing: the app port
is open to the internet, and anyone who finds it will spend your API credits.

---

## Project layout

```
app.py                  web layer, session memory
agents/
  orchestrator.py       decides which specialist answers
  fraud_agent.py        transaction fraud
  loan_agent.py         credit assessment
  compliance_agent.py   KYC and sanctions
  support_agent.py      policy questions
mcp/
  fraud_tools.py        MCP server — transactions, day scan, ServiceNow
  loan_tools.py         MCP server — applications, affordability ratios
  compliance_tools.py   MCP server — KYC, sanctions screening
  support_tools.py      MCP server — policy search
rag/
  policy_index.py       shared retrieval over the policy documents
scripts/                one-off data preparation
data/                   generated JSON the MCP servers read
infra/                  Terraform
static/index.html       the chat page
```

---

## Notes and known limits

**Sessions live in memory.** They are lost when the server restarts and would not
survive more than one instance. Redis or DynamoDB would fix that.

**MCP servers are spawned per request.** Each question starts a fresh Python process
that reloads its data. Fine locally, wasteful in production — running the MCP servers
as long-lived HTTP services would remove it.

**The policy index is built ahead of time.** Edit a policy document and you must
re-run `build_policy_index.py`, or the index still holds the old text.

**Recommendations are not decisions.** The loan agent advises; it cannot record an
outcome. The fraud agent asks before opening a ticket. Neither is a control you should
rely on in production — they are prompt instructions, not enforced permissions.
