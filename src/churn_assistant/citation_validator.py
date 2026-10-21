from .risk_engine import DRIVER_ORDER

def validate_citations(response: dict, retrieved_records: list[dict], policies: list[dict]):
    eligible = {
        r["record_id"] for r in retrieved_records if r.get("verified") is True
    } | {
        p["doc_id"] for p in policies if p.get("verified") is True
    }
    errors = []
    for driver in response.get("drivers", []):
        for citation in driver.get("citations", []):
            if citation not in eligible:
                errors.append(f"Invalid driver citation: {citation}")
    action = response.get("recommended_action")
    if action:
        for citation in action.get("citations", []):
            if citation not in eligible:
                errors.append(f"Invalid action citation: {citation}")
    names = [d.get("driver") for d in response.get("drivers", [])]
    if names != sorted(names, key=lambda x: DRIVER_ORDER.index(x) if x in DRIVER_ORDER else 999):
        errors.append("Driver categories are not in the required fixed order.")
    risk = response.get("risk", {})
    score = risk.get("score")
    expected = None if score is None else ("low" if score <= 2 else "medium" if score <= 5 else "high")
    if risk.get("level") != expected:
        errors.append("Risk level does not match deterministic score.")
    if response.get("escalate") and not response.get("escalation_reason"):
        errors.append("escalate=true requires escalation_reason.")
    if action and action.get("action") not in {"plan_review", "network_escalation", "bill_correction", "callback"}:
        errors.append("Recommended action is outside the fixed catalog.")
    return errors
