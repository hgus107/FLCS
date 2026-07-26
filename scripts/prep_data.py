# DATA PREP: one-off script. Cuts the large Kaggle fraud CSV down to a few
# customers and writes the small JSON files the MCP server reads at startup.
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

# REQUIREMENT: the full Kaggle file is too big for an LLM, so pull a handful of
# customers who have at least one confirmed fraud, and keep their history readable.
RAW = Path("data/raw/fraudTest.csv")
N_CUSTOMERS = 8
MAX_TX = 40

rows_by_cc = defaultdict(list)
with RAW.open() as f:
    for r in csv.DictReader(f):
        rows_by_cc[r["cc_num"]].append(r)

fraudy = [cc for cc, rs in rows_by_cc.items() if any(r["is_fraud"] == "1" for r in rs)]
random.seed(0)
picked = random.sample(fraudy, min(N_CUSTOMERS, len(fraudy)))

transactions, customers, labels = [], [], {}

for i, cc in enumerate(picked, 1):
    cid = f"C{i:03d}"
    rs = rows_by_cc[cc]

    frauds = [r for r in rs if r["is_fraud"] == "1"][:5]
    normals = [r for r in rs if r["is_fraud"] == "0"][: MAX_TX - len(frauds)]
    chosen = sorted(frauds + normals, key=lambda r: r["trans_date_trans_time"])

    c0 = rs[0]
    customers.append({
        "customer_id": cid,
        "name": f'{c0["first"]} {c0["last"]}',
        "gender": c0["gender"],
        "city": c0["city"],
        "state": c0["state"],
        "job": c0["job"],
        "dob": c0["dob"],
    })

    for j, r in enumerate(chosen, 1):
        tid = f"TX{i:03d}{j:03d}"
        date, time = r["trans_date_trans_time"].split(" ")
        transactions.append({
            "transaction_id": tid,
            "customer_id": cid,
            "amount": float(r["amt"]),
            "merchant": r["merchant"].replace("fraud_", ""),
            "category": r["category"],
            "city": r["city"],
            "state": r["state"],
            "date": date,
            "time": time,
        })
        # REQUIREMENT: keep the ground-truth label out of the agent's reach so it
        # has to actually reason; kept separately for scoring later.
        labels[tid] = int(r["is_fraud"])

Path("data/transactions.json").write_text(json.dumps(transactions, indent=2))
Path("data/customers.json").write_text(json.dumps(customers, indent=2))
Path("data/labels.json").write_text(json.dumps(labels, indent=2))

print(f"{len(customers)} customers, {len(transactions)} transactions")