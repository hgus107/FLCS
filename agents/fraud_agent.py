# AGENT: takes a question from the UI or CLI, sends it to the LLM along with the
# list of tools the MCP server offers, runs whichever tool the LLM picks, feeds the
# result back, and repeats until the LLM answers in plain text. Carries the previous
# turns in and out so a follow-up like "yes, open it" still has context.

import asyncio
import json
import os
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = "claude-haiku-4-5"

SYSTEM = (
    "You are a fraud analyst assistant for a bank. "
    "Use the available tools to scan a day's transactions, look up transactions, "
    "customer profiles and customer history, and to open fraud tickets. "
    "When you find something suspicious, explain your reasoning and then ASK the "
    "analyst whether to open a ticket. Never call create_fraud_case until the "
    "analyst has explicitly confirmed it in their message. "
    "Answer in plain English once you have the data."
)


def to_claude_tools(mcp_tools):
    # REQUIREMENT: the LLM cannot read MCP objects, so each MCP tool is rewritten
    # into the {name, description, input_schema} shape the Messages API expects.
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]


def flatten(mcp_result):
    # REQUIREMENT: MCP returns a list of content blocks; the LLM needs one string.
    parts = [b.text for b in mcp_result.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts) or json.dumps({"error": "empty tool result"})


async def run(user_request: str, history: list | None = None):
    """Returns (answer_text, updated_history)."""
    llm = anthropic.Anthropic()

    # sys.executable = this venv's python, so the MCP server gets the same packages.
    server = StdioServerParameters(
        command=sys.executable, args=["mcp/banking_tools.py"]
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:

            # REQUEST OUT: handshake with the MCP server.
            await session.initialize()

            # REQUEST OUT: ask the MCP server what it can do.
            listed = await session.list_tools()
            # RESPONSE IN: the server's tool catalogue.
            tools = to_claude_tools(listed.tools)
            print("AVAILABLE TOOLS:", [t["name"] for t in tools])

            # REQUIREMENT: start from the previous turns so the analyst can say "yes"
            # and the model still knows what it offered to do.
            messages = list(history or [])
            messages.append({"role": "user", "content": user_request})

            # REQUIREMENT: keep looping while the model still wants tools; each pass is
            # ask the model -> run whatever it picked -> hand the results back.
            while True:
                # REQUEST OUT: send the tool catalogue plus the conversation to the model.
                reply = llm.messages.create(
                    model=MODEL,
                    max_tokens=4000,
                    system=SYSTEM,
                    tools=tools,
                    messages=messages,
                )
                # RESPONSE IN: either final text, or tool_use blocks naming the calls to make.

                messages.append({"role": "assistant", "content": reply.content})

                if reply.stop_reason != "tool_use":
                    break

                results = []
                for block in reply.content:
                    if block.type != "tool_use":
                        continue
                    print(f"MODEL CHOSE: {block.name}({block.input})")

                    # REQUEST OUT: execute the model's chosen tool on the MCP server.
                    out = await session.call_tool(block.name, block.input)
                    # RESPONSE IN: the real banking data.
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": flatten(out),
                        }
                    )

                messages.append({"role": "user", "content": results})

            answer = "\n".join(b.text for b in reply.content if b.type == "text")
            return answer, messages


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY first.")

    # In production this string arrives from the chat UI instead of being hardcoded.
    text, _ = asyncio.run(run("Scan the latest day and give me the 1 most suspicious transaction."))
    print(text)