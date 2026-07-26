# MCP SERVER: exposes the bank's data as tools the agent can call — scan a day's
# transactions for suspicious ones, look up a transaction, a customer or their
# history, and open a fraud ticket in ServiceNow.

import json
import os
from collections import defaultdict
from statistics import mean

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

SN_URL = os.getenv("SERVICENOW_URL")
SN_USER = os.getenv("SERVICENOW_USER")
SN_PASS = os.getenv("SERVICENOW_PASSWORD")

mcp = FastMCP("FLCS Banking Tools")

with open("data/transactions.json") as f:
    transactions = json.load(f)

with open("data/customers.json") as f:
    customers = json.load(f)

# REQUIREMENT: build each customer's normal spending profile once at startup, so the
# day scan can compare against it without re-reading the whole file per transaction.
profile = defaultdict(lambda: {"amounts": [], "cities": set(), "categories": set()})
for tx in transactions:
    p = profile[tx["customer_id"]]
    p["amounts"].append(tx["amount"])
    p["cities"].add(tx["city"])
    p["categories"].add(tx["category"])


@mcp.tool()
def scan_day(date: str = "", limit: int = 5):
    """Scan one day's transactions and return the most suspicious ones with reasons.
    Pass a date as YYYY-MM-DD, or leave blank for the most recent day in the data.
    Set limit to how many suspicious transactions to return."""
    # REQUIREMENT: a real bank drops hundreds of thousands of rows a night. Scoring
    # happens here in plain Python; the LLM only ever sees the short list, never the
    # full file — that is what keeps this affordable and inside the context window.
    days = sorted({tx["date"] for tx in transactions})
    if not date or date.lower() in ("latest", "yesterday"):
        date = days[-1]

    todays = [tx for tx in transactions if tx["date"] == date]
    if not todays:
        return {"error": f"No transactions on {date}", "available_dates": days[-10:]}

    per_customer_today = defaultdict(int)
    for tx in todays:
        per_customer_today[tx["customer_id"]] += 1

    scored = []
    for tx in todays:
        p = profile[tx["customer_id"]]
        avg = mean(p["amounts"]) if p["amounts"] else tx["amount"]
        hour = int(tx["time"].split(":")[0])

        score, reasons = 0, []

        if avg and tx["amount"] > 5 * avg:
            score += 3
            reasons.append(
                f"${tx['amount']:.2f} is {tx['amount'] / avg:.1f}x this customer's "
                f"average of ${avg:.2f}"
            )

        if hour >= 22 or hour <= 5:
            score += 2
            reasons.append(f"booked at {tx['time']}, outside normal waking hours")

        if tx["city"] not in p["cities"]:
            score += 2
            reasons.append(f"{tx['city']}, {tx['state']} is not a city this customer uses")

        if tx["amount"] > 1000:
            score += 1
            reasons.append(f"high value at ${tx['amount']:.2f}")

        if per_customer_today[tx["customer_id"]] >= 4:
            score += 1
            reasons.append(
                f"{per_customer_today[tx['customer_id']]} transactions from this "
                f"customer on the same day"
            )

        if score:
            scored.append(
                {
                    "transaction_id": tx["transaction_id"],
                    "customer_id": tx["customer_id"],
                    "amount": tx["amount"],
                    "merchant": tx["merchant"],
                    "category": tx["category"],
                    "city": tx["city"],
                    "time": tx["time"],
                    "risk_score": score,
                    "reasons": reasons,
                }
            )

    scored.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "date_scanned": date,
        "transactions_scanned": len(todays),
        "flagged": len(scored),
        "returned": scored[:limit],
    }


@mcp.tool()
def get_transaction(transaction_id: str):
    """Fetch details of a single transaction by its ID"""
    for tx in transactions:
        if tx["transaction_id"] == transaction_id:
            return tx

    return {"error": "Transaction not found"}


@mcp.tool()
def get_customer(customer_id: str):
    """Fetch a customer's profile: name, gender, city, state, job, date of birth"""
    for c in customers:
        if c["customer_id"] == customer_id:
            return c

    return {"error": "Customer not found"}


@mcp.tool()
def get_customer_transactions(customer_id: str):
    """Fetch a customer's full transaction history"""
    return [tx for tx in transactions if tx["customer_id"] == customer_id]


@mcp.tool()
def create_fraud_case(transaction_id: str, reason: str):
    """Open a fraud investigation ticket in ServiceNow for a suspicious transaction"""
    # REQUIREMENT: credentials live in .env and never in the prompt or the agent,
    # so the LLM can trigger a ticket without ever seeing the password.
    if not (SN_URL and SN_USER and SN_PASS):
        return {"error": "ServiceNow credentials missing from .env"}

    resp = requests.post(
        f"{SN_URL}/api/now/table/incident",
        auth=(SN_USER, SN_PASS),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={
            "short_description": f"Suspected fraud on transaction {transaction_id}",
            "description": reason,
            "urgency": "2",
        },
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        return {"error": f"ServiceNow returned {resp.status_code}", "body": resp.text[:300]}

    r = resp.json()["result"]
    return {
        "status": "created",
        "ticket_number": r["number"],
        "link": f"{SN_URL}/nav_to.do?uri=incident.do?sys_id={r['sys_id']}",
        "transaction_id": transaction_id,
        "reason": reason,
    }


if __name__ == "__main__":
    mcp.run()