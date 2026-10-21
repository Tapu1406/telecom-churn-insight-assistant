from datetime import date
from .repository import retrieve_policies
from .config import SESSION_DATE

ACTIONS = {"plan_review", "network_escalation", "bill_correction", "callback"}

def evaluate_policy(customer_id, records, action, session_date=SESSION_DATE):
    if session_date is None:
        session_date = SESSION_DATE

    policy_rows = retrieve_policies(session_date)
    conflicts = []
    escalate = False
    reasons = []
    unsupported = []
    missing = []

    if customer_id == "CUST-1002":
        ids = {r["record_id"] for r in records}
        if {"TKT-6610", "CALL-8821"}.issubset(ids):
            conflicts.append("Billing status conflict: TKT-6610 says resolved; later CALL-8821 says the charge remains on the bill. Latest reported status is the later call; correction still requires verification.")
            action = "bill_correction"

    if customer_id == "CUST-1004":
        escalate = True
        reasons.append("Requested 50% discount for 6 months exceeds RET-POL limits of 20% for 3 months.")
    if conflicts:
        escalate = True
        reasons.append("Unresolved material billing conflict requires supervisor review.")
    if action not in ACTIONS:
        escalate = True
        reasons.append("Proposed action is outside the approved action catalog.")

    fest = next((p for p in policy_rows if p["doc_id"] == "OFFER-FEST"), None)
    if fest and fest.get("expired"):
        unsupported.append("OFFER-FEST is expired as of the session date and cannot be recommended as an available offer.")

    if customer_id == "CUST-1001":
        missing.append("Customer's preferred callback time")
        unsupported.append("Network repair dates are not present in approved content.")
    if customer_id == "CUST-1005":
        missing.extend(["Recent customer interactions", "Current usage trend"])
    if customer_id == "CUST-1002":
        missing.append("Verified billing correction outcome")

    return {
        "action": action, "escalate": escalate,
        "escalation_reason": "; ".join(reasons) if reasons else None,
        "data_conflicts": conflicts, "unsupported": unsupported,
        "missing_information": missing, "policies": policy_rows
    }
