# MCP SERVER: exposes the bank's policy library as tools the support agent can call.
# Unlike the other servers it holds no customer data — support answers "what is the
# rule" questions, and searches all four rulebooks rather than just one.

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# REQUIREMENT: this file is launched as a script from mcp/, so the project root is
# not on the import path until we put it there.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag.policy_index import search as policy_search

mcp = FastMCP("FLCS Support Tools")

AREAS = ("fraud", "lending", "compliance", "support")


@mcp.tool()
def search_policy(question: str):
    """Search every bank policy for the rules covering a customer question —
    disputes, lost cards, blocks, fees, complaints, escalation, verification,
    vulnerable customers. Use this for any question about what the bank's rules say."""
    return policy_search(question, k=4)


@mcp.tool()
def search_policy_area(question: str, area: str):
    """Search one rulebook only. Area must be one of: fraud, lending, compliance,
    support. Use this when the question clearly belongs to a single area and the
    general search is returning material from the wrong one."""
    if area not in AREAS:
        return {"error": f"area must be one of {', '.join(AREAS)}"}

    return policy_search(question, area=area, k=4)


@mcp.tool()
def list_policy_documents():
    """List the policy documents available to search, with the area each covers"""
    return [
        {"document": "fraud_policy.md", "area": "fraud",
         "covers": "detection thresholds, structuring, investigations, cases, liability, card blocks"},
        {"document": "lending_policy.md", "area": "lending",
         "covers": "credit bands, affordability ratios, referrals, hardship, fair lending"},
        {"document": "compliance_policy.md", "area": "compliance",
         "covers": "KYC, risk ratings, PEPs, sanctions screening, reporting, account changes"},
        {"document": "support_policy.md", "area": "support",
         "covers": "disputes, lost cards, fees, complaints, disclosure limits, vulnerable customers"},
    ]


if __name__ == "__main__":
    mcp.run()