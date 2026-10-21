import json
from pathlib import Path
from datetime import date
from .config import DATA_DIR

def _load(name: str):
    path = Path(DATA_DIR) / name
    if not path.exists():
        # Also support running from a different working directory.
        path = Path(__file__).resolve().parents[2] / "data" / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def customers():
    return _load("customers.json")

def records():
    return _load("interaction_records.json")

def policies():
    return _load("policies.json")

def get_customer(customer_id: str):
    return next((c for c in customers() if c["customer_id"] == customer_id), None)

def retrieve_customer_records(customer_id: str):
    return [r for r in records() if r["customer_id"] == customer_id and r.get("verified") is True]

def retrieve_policies(session_date: date):
    result = []
    for p in policies():
        item = dict(p)
        if p.get("doc_id") == "OFFER-FEST":
            item["expired"] = session_date > date.fromisoformat(p["expires"])
        result.append(item)
    return result
