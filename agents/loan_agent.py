# AGENT: takes a lending question from the orchestrator or CLI, sends it to the LLM
# along with the tools the loan MCP server offers, runs whichever tool the LLM picks,
# feeds the result back, and repeats until the LLM answers in plain text.

import asyncio
import json
import os
import sys

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MODEL = "claude-haiku-4-5"

SYSTEM = (
    "You are a credit analyst assistant for a bank. "
    "Use the available tools to look up loan applications, a customer's borrowing "
    "history, applications awaiting a decision, and customer profiles. "
    "The tools already calculate the affordability ratios — judge them, do not "
    "recalculate them. "
    "Give a clear recommendation with your reasoning: approve, decline, or refer "
    "for manual review. Never claim a decision has been recorded — you can only "
    "advise. Answer in plain English once you have the data."
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
        command=sys.executable, args=["mcp/loan_tools.py"]
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:

            # REQUEST OUT: handshake with the MCP server.
            await session.initialize()

            # REQUEST OUT: ask the MCP server what it can do.
            listed = await session.list_tools()
            # RESPONSE IN: the server's tool catalogue.
            tools = to_claude_tools(listed.tools)
            print("LOAN TOOLS:", [t["name"] for t in tools])

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
                    print(f"LOAN AGENT CHOSE: {block.name}({block.input})")

                    # REQUEST OUT: execute the model's chosen tool on the MCP server.
                    out = await session.call_tool(block.name, block.input)
                    # RESPONSE IN: the real lending data.
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": flatten(out),
                        }
                    )

                messages.append({"role": "user", "content": results})

            return "\n".join(b.text for b in reply.content if b.type == "text"), messages


if __name__ == "__main__":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY first.")

    text, _ = asyncio.run(run("List the pending loan applications and recommend a decision on one of them."))
    print(text)