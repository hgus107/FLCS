# DATA PREP: one-off script. Converts the real OFAC sanctions list into JSON the
# compliance MCP server can search, and generates KYC records for the same 8
# customers the fraud and loan agents already know about.

import csv
import json
import random
from pathlib import Path

SDN = Path("data/raw/sdn.csv")

customers = json.loads(Path("data/customers.json").read_text())

# REQUIREMENT: SDN.CSV ships with no header row and uses "-0-" for empty fields.
COLUMNS = [
    "ent_num", "name", "type", "program", "title", "call_sign", "vess_type",
    "tonnage", "grt", "vess_flag", "vess_owner", "remarks",
]

sanctions = []
with SDN.open(encoding="latin-1") as f:
    for row in csv.DictReader(f, fieldnames=COLUMNS):
        name = (row["name"] or "").strip()
        if not name or name == "-0-":
            continue
        sanctions.append(
            {
                "name": name,
                "type": (row["type"] or "").strip().replace("-0-", ""),
                "program": (row["program"] or "").strip().replace("-0-", ""),
            }
        )
# REQUIREMENT: the full OFAC list is 19k names, which makes a 50-applicant scan a
# million string comparisons. For a demo, keep a 99-name sample — real entries,
# just fewer of them.
random.seed(0)
sanctions = random.sample(sanctions, 99)

# Plant exactly one entry matching C003 so the screening demo has something to find.
# Marked so nobody mistakes it for real OFAC data.
planted = customers[2]["name"]
sanctions.append(
    {
        "name": planted.upper(),
        "type": "individual",
        "program": "DEMO-PLANTED (not real OFAC data)",
    }
)
print(f"Planted sanctions entry for {planted} (C003)")

Path("data/sanctions.json").write_text(json.dumps(sanctions, indent=2))

# REQUIREMENT: no public KYC dataset exists — it is all personal data — so generate
# plausible records. Seeded so the demo tells the same story every run, and C005 is
# deliberately non-compliant to match the fraud and credit findings on that customer.
random.seed(0)

ID_TYPES = ["Passport", "Driving Licence", "National ID"]
RISK = ["Low", "Low", "Low", "Medium", "Medium", "High"]

kyc = []
for c in customers:
    expired = c["customer_id"] == "C005"

    kyc.append(
        {
            "customer_id": c["customer_id"],
            "name": c["name"],
            "id_type": random.choice(ID_TYPES),
            "id_number": f"****{random.randint(1000, 9999)}",
            "id_expiry": "2019-08-14" if expired else f"20{random.randint(27, 32)}-0{random.randint(1, 9)}-1{random.randint(0, 9)}",
            "address_verified": not expired,
            "pep": False,
            "risk_rating": "High" if expired else random.choice(RISK),
            "last_review_date": "2018-03-02" if expired else f"202{random.randint(4, 5)}-0{random.randint(1, 9)}-1{random.randint(0, 9)}",
        }
    )

Path("data/kyc.json").write_text(json.dumps(kyc, indent=2))

print(f"{len(sanctions)} sanctions entries, {len(kyc)} KYC records")