# MCP SERVER: exposes the bank's compliance data as tools the compliance agent can
# call — list pending credit-card applications, pull a customer's KYC record, screen
# a name against the OFAC sanctions list, or run all of those across every applicant.

import sys
from pathlib import Path

# REQUIREMENT: this file is launched as a script from mcp/, so the project root is
# not on the import path until we put it there.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag.policy_index import search as policy_search

import json
from datetime import date
from difflib import SequenceMatcher

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("FLCS Compliance Tools")

with open("data/card_applications.json") as f:
    applications = json.load(f)

with open("data/kyc.json") as f:
    kyc_records = json.load(f)

with open("data/sanctions.json") as f:
    sanctions = json.load(f)

KYC_BY_CUSTOMER = {k["customer_id"]: k for k in kyc_records}

# REQUIREMENT: pre-uppercase the 19k sanctions names once at startup rather than on
# every comparison, or a full scan takes minutes instead of seconds.
SANCTION_NAMES = [(s["name"].upper(), s) for s in sanctions]


def _screen(name: str, cutoff: float = 0.87):
    # REQUIREMENT: real sanctions screening is fuzzy — people vary spelling and word
    # order deliberately. Exact matching alone would miss almost every real hit.
    target = name.upper()
    hits = []

    for candidate, entry in SANCTION_NAMES:
        score = SequenceMatcher(None, target, candidate).ratio()
        if score >= cutoff:
            hits.append(
                {
                    "matched_name": entry["name"],
                    "program": entry["program"],
                    "type": entry["type"],
                    "similarity": round(score, 3),
                }
            )

    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return hits[:5]


def _kyc_issues(record):
    issues = []

    if record["id_expiry"] < date.today().isoformat():
        issues.append(f"ID expired on {record['id_expiry']}")

    if not record["address_verified"]:
        issues.append("address not verified")

    if record["risk_rating"] == "High":
        issues.append("customer rated High risk")

    if record["pep"]:
        issues.append("politically exposed person")

    return issues


@mcp.tool()
def list_pending_card_applications():
    """List every credit-card application awaiting a compliance decision"""
    return [a for a in applications if a["status"] == "Pending"]


@mcp.tool()
def get_kyc(customer_id: str):
    """Fetch a customer's KYC record: ID type, expiry, address verification, risk rating"""
    record = KYC_BY_CUSTOMER.get(customer_id)
    if not record:
        return {"error": f"No KYC record on file for {customer_id}"}

    return {**record, "issues": _kyc_issues(record)}


@mcp.tool()
def screen_name(name: str):
    """Screen one name against the OFAC sanctions list, returning any close matches"""
    hits = _screen(name)
    return {"name": name, "matches": hits, "clear": not hits}

@mcp.tool()
def search_policy(question: str):
    """Search the bank's compliance policy for the rules covering a question — KYC
    requirements, risk ratings, PEPs, sanctions screening and how to handle a match,
    reporting thresholds, account changes, escalation. Use this whenever the answer
    depends on a bank rule rather than on the customer data."""
    return policy_search(question, area="compliance")

@mcp.tool()
def run_compliance_scan():
    """Run KYC and sanctions checks across every pending card application and return
    only the ones with findings, plus counts."""
    # REQUIREMENT: 50 applications against 19k sanctions names is far too much to put
    # in front of the model. The checking happens here; the LLM sees only the
    # exceptions and the totals.
    flagged = []
    with_kyc = 0

    for app in [a for a in applications if a["status"] == "Pending"]:
        findings = []

        record = KYC_BY_CUSTOMER.get(app["customer_id"]) if app["customer_id"] else None
        if record:
            with_kyc += 1
            findings.extend(_kyc_issues(record))
        else:
            findings.append("no KYC record on file")

        hits = _screen(app["name"])
        if hits:
            findings.append(
                f"sanctions match: {hits[0]['matched_name']} "
                f"({hits[0]['program']}, similarity {hits[0]['similarity']})"
            )

        if findings:
            flagged.append(
                {
                    "application_id": app["application_id"],
                    "customer_id": app["customer_id"],
                    "name": app["name"],
                    "findings": findings,
                    "sanctions_hit": bool(hits),
                }
            )

    return {
        "applications_scanned": len([a for a in applications if a["status"] == "Pending"]),
        "with_kyc_on_file": with_kyc,
        "flagged": len(flagged),
        "sanctions_hits": len([f for f in flagged if f["sanctions_hit"]]),
        "details": flagged,
    }


if __name__ == "__main__":
    mcp.run()