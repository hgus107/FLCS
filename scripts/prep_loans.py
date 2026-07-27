# DATA PREP: one-off script. Samples real loan applications from the Kaggle file and
# attaches them to the same 8 customers the fraud agent already knows about, so both
# agents are talking about the same people.

import csv
import json
import random
from pathlib import Path

RAW = Path("data/raw/loan_approval_dataset.csv")
LOANS_PER_CUSTOMER = 2

# REQUIREMENT: the Kaggle file is in rupees. Scale to dollars so loan amounts read
# sensibly next to the dollar transactions the fraud agent already reports.
INR_TO_USD = 80

customers = json.loads(Path("data/customers.json").read_text())

# The Kaggle export has a leading space in every column name — strip them.
with RAW.open() as f:
    rows = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(f)]

random.seed(0)
picked = random.sample(rows, len(customers) * LOANS_PER_CUSTOMER)

ASSET_COLUMNS = (
    "residential_assets_value",
    "commercial_assets_value",
    "luxury_assets_value",
    "bank_asset_value",
)

loans = []
i = 0

for c in customers:
    for n in range(LOANS_PER_CUSTOMER):
        r = picked[i]
        i += 1

        assets = sum(int(r[k]) for k in ASSET_COLUMNS)

        # REQUIREMENT: leave each customer's most recent application Pending, so the
        # agent has a live decision to reason about rather than only history.
        status = "Pending" if n == LOANS_PER_CUSTOMER - 1 else r["loan_status"]

        loans.append(
            {
                "loan_id": f"LN{c['customer_id'][1:]}{n + 1:02d}",
                "customer_id": c["customer_id"],
                "amount": round(int(r["loan_amount"]) / INR_TO_USD),
                "term_years": int(r["loan_term"]),
                "annual_income": round(int(r["income_annum"]) / INR_TO_USD),
                "credit_score": int(r["cibil_score"]),
                "education": r["education"],
                "self_employed": r["self_employed"],
                "dependents": int(r["no_of_dependents"]),
                "total_assets": round(assets / INR_TO_USD),
                "status": status,
            }
        )

Path("data/loans.json").write_text(json.dumps(loans, indent=2))
print(f"{len(loans)} loans for {len(customers)} customers")