# DATA PREP: one-off script. Samples 50 rows from the Kaggle credit-card application
# file into a small JSON the compliance MCP server can read. The first 8 are given
# your existing customer ids so compliance, fraud and loan all talk about the same
# people; the other 42 are strangers with no KYC on file.

import csv
import json
import random
from itertools import islice
from pathlib import Path

RAW = Path("data/raw/application_record.csv")
TOTAL = 50

customers = json.loads(Path("data/customers.json").read_text())

random.seed(0)

FIRST = ["Marcus", "Elena", "Priya", "Tobias", "Aisha", "Diego", "Nora", "Kenji",
         "Rosa", "Ivan", "Leila", "Omar", "Freya", "Hugo", "Mira", "Sven"]
LAST = ["Whitfield", "Okonkwo", "Lindqvist", "باقري".encode("ascii", "ignore").decode() or "Bakri",
        "Moreau", "Castellanos", "Dubois", "Nakamura", "Petrov", "Haddad",
        "Andersson", "Rivera", "Kowalski", "Mensah", "Bianchi", "Novak"]

with RAW.open() as f:
    rows = list(islice(csv.DictReader(f), TOTAL))

applications = []

for i, r in enumerate(rows):
    # REQUIREMENT: the first 8 applications belong to customers the other agents
    # already know. The rest are strangers, so a KYC lookup on them comes back empty
    # — which is the point of the scan.
    if i < len(customers):
        c = customers[i]
        customer_id, name = c["customer_id"], c["name"]
    else:
        customer_id = None
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"

    age_years = abs(int(r["DAYS_BIRTH"])) // 365

    applications.append(
        {
            "application_id": f"CC{i + 1:04d}",
            "customer_id": customer_id,
            "name": name,
            "annual_income": round(float(r["AMT_INCOME_TOTAL"])),
            "income_type": r["NAME_INCOME_TYPE"],
            "education": r["NAME_EDUCATION_TYPE"],
            "family_status": r["NAME_FAMILY_STATUS"],
            "housing": r["NAME_HOUSING_TYPE"],
            "occupation": r["OCCUPATION_TYPE"] or "Not stated",
            "age_years": age_years,
            "status": "Pending",
        }
    )

Path("data/card_applications.json").write_text(json.dumps(applications, indent=2))
print(f"{len(applications)} card applications, {len(customers)} tied to known customers")