# ORCHESTRATOR AGENT: takes the analyst's question from the UI, decides which
# specialist agent should handle it, delegates, and relays the answer back.
# It never touches banking data itself — its tools are the other agents.

import asyncio
import os
import sys
from pathlib import Path

import anthropic

# REQUIREMENT: works whether started via app.py or run directly from the terminal.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.fraud_agent import run as fraud_run

MODEL = "claude-haiku-4-5"

SYSTEM = (
    "You are the front desk for a bank's AI assistants. You have no access to "
    "banking data yourself. Work out which specialist agent can answer the "
    "analyst's question, delegate to it, and relay what comes back. "
    "The specialists have no memory of this conversation, so when you delegate, "
    "write a self-contained instruction — restate any transaction id, customer id "
    "or decision the specialist needs. "
    "If a specialist asks a question back, put it to the analyst as it stands."
)

# REQUIREMENT: one entry per specialist agent. Adding a Loan or Compliance agent
# later means adding a dict here and a branch in call_agent — the loop below is
# unchanged, exactly like adding a tool to the MCP server.
TOOLS = [
    {
        "name": "ask_fraud_agent",
        "description": (
            "Send a question to the fraud analyst agent. It can scan a day's "
            "transactions for suspicious activity, look up a transaction, a "
            "customer profile or a customer's full history, and open fraud "
            "tickets in ServiceNow. Use it for anything about suspicious "
            "transactions, fraud investigations, or fraud tickets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "A self-contained instruction for the fraud agent.",
                }
            },
            "required": ["question"],
        },
    }
]


async def call_agent(name: str, args: dict) -> str:
    if name == "ask_fraud_agent":
        # REQUEST OUT: hand the instruction down to the fraud agent, which runs its
        # own loop against MCP and comes back with finished text.
        answer, _ = await fraud_run(args["question"])
        return answer

    return f"No such agent: {name}"


async def run(user_request: str, history: list | None = None):
    """Returns (answer_text, updated_history)."""
    llm = anthropic.Anthropic()

    messages = list(history or [])
    messages.append({"role": "user", "content": user_request})

    # REQUIREMENT: same loop as the fraud agent, one level up — the only difference
    # is that a "tool" here is an entire agent rather than a database lookup.
    while True:
        # REQUEST OUT: send the agent roster plus the conversation to the model.
        reply = llm.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        # RESPONSE IN: either the final reply, or a request to delegate.

        messages.append({"role": "assistant", "content": reply.content})

        if reply.stop_reason != "tool_use":
            break

        results = []
        for block in reply.content:
            if block.type != "tool_use":
                continue
            print(f"ORCHESTRATOR DELEGATED TO: {block.name}")

            out = await call_agent(block.name, block.input)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": out,
                }
            )

        messages.append({"role": "user", "content": results})

    answer = "\n".join(b.text for b in reply.content if b.type == "text")
    return answer, messages


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY first.")

    text, _ = asyncio.run(run("Scan the latest day and give me the 1 most suspicious transaction."))
    print(text)