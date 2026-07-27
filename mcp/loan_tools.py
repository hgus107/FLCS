# MCP SERVER: exposes the bank's lending data as tools the loan agent can call —
# look up an application, a customer's borrowing history, or everything still pending.

import sys
from pathlib import Path

# REQUIREMENT: this file is launched as a script from mcp/, so the project root is
# not on the import path until we put it there.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag.policy_index import search as policy_search

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("FLCS Loan Tools")

with open("data/loans.json") as f:
    loans = json.load(f)

with open("data/customers.json") as f:
    customers = json.load(f)


def _with_ratios(loan):
    # REQUIREMENT: compute the standard lending ratios here rather than asking the
    # model to do arithmetic — it should judge the numbers, not calculate them.
    income = loan["annual_income"] or 1
    annual_repayment = loan["amount"] / max(loan["term_years"], 1)

    return {
        **loan,
        "loan_to_income": round(loan["amount"] / income, 2),
        "annual_repayment": round(annual_repayment),
        "repayment_to_income_pct": round(100 * annual_repayment / income, 1),
        "assets_to_loan": round(loan["total_assets"] / max(loan["amount"], 1), 2),
    }


@mcp.tool()
def get_loan_application(loan_id: str):
    """Fetch one loan application by its ID, with affordability ratios calculated"""
    for loan in loans:
        if loan["loan_id"] == loan_id:
            return _with_ratios(loan)

    return {"error": "Loan application not found"}


@mcp.tool()
def get_customer_loans(customer_id: str):
    """Fetch every loan application belonging to a customer, past and pending"""
    return [_with_ratios(loan) for loan in loans if loan["customer_id"] == customer_id]


@mcp.tool()
def list_pending_applications():
    """List every loan application currently awaiting a decision"""
    return [_with_ratios(loan) for loan in loans if loan["status"] == "Pending"]

@mcp.tool()
def search_policy(question: str):
    """Search the bank's lending policy for the rules covering a question — credit
    score bands, affordability thresholds, referral triggers, hardship, prohibited
    grounds. Use this whenever the answer depends on a bank rule rather than on the
    application data."""
    return policy_search(question, area="lending")

@mcp.tool()
def get_customer(customer_id: str):
    """Fetch a customer's profile: name, gender, city, state, job, date of birth"""
    for c in customers:
        if c["customer_id"] == customer_id:
            return c

    return {"error": "Customer not found"}


if __name__ == "__main__":
    mcp.run()