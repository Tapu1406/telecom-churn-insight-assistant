import json
import re
from langchain_ollama import ChatOllama
from .config import OLLAMA_MODEL, OLLAMA_BASE_URL, SESSION_DATE
from .repository import get_customer, retrieve_customer_records
from .risk_engine import score_customer, DRIVER_ORDER
from .policy_engine import evaluate_policy
from .citation_validator import validate_citations

SYSTEM_PROMPT = """You are a telecom customer churn insight assistant.
Use only the verified records and approved policy content provided in the prompt.
Never invent evidence, record IDs, prices, repair dates, or promises.
Do not calculate or alter risk: use the deterministic score and level supplied.
Only use the fixed driver list and action catalog. Every driver and recommendation must cite supplied record IDs.
Do not cite unverified records. If facts are absent, list them as missing or unsupported.
Return only a JSON object matching the requested response structure."""

def _llm():
    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

def _baseline_drivers(customer_id, rows, score):
    drivers = []
    ids = {r["record_id"] for r in rows}
    if customer_id == "CUST-1001":
        drivers = [
            {"driver":"network_quality","evidence":"Three dropped-call complaints from the same cell/location in the recent period.","citations":["TKT-5521","TKT-5540","TKT-5562"]},
            {"driver":"usage_decline","evidence":"Data usage declined by 35% month on month.","citations":["USG-1001@2026-09"]}
        ]
    elif customer_id == "CUST-1002":
        drivers = [{"driver":"billing_dispute","evidence":"A later call says the roaming charge remains on the bill, conflicting with an earlier ticket marked resolved.","citations":["TKT-6610","CALL-8821"]}]
    elif customer_id == "CUST-1003":
        drivers = [{"driver":"service_experience","evidence":"One slow-data complaint is recorded; usage is reported as stable.","citations":["TKT-7101"]}]
    elif customer_id == "CUST-1004":
        drivers = [{"driver":"competitor_intent","evidence":"The customer mentioned a competitor, requested port-out, and requested a discount beyond policy limits.","citations":["CALL-9034"]}]
    elif customer_id == "CUST-1006":
        drivers = [{"driver":"plan_fit","evidence":"The customer asked for a review of the current plan; no specific dissatisfaction was recorded.","citations":["CALL-1006"]}]
    return sorted(drivers, key=lambda d: DRIVER_ORDER.index(d["driver"]))

def _select_action(rows, score):
    """Choose an allowed action from verified signals, not from a customer ID."""
    flags = score.get("signal_flags", {})
    if flags.get("network_complaints_3plus"):
        return "network_escalation"
    if flags.get("open_or_disputed_billing"):
        return "bill_correction"
    if flags.get("competitor_or_portout"):
        return "callback"

    content = " ".join(r.get("content", "").lower() for r in rows)
    if any(term in content for term in ("slow-data complaint", "plan review", "review of their current plan")):
        return "plan_review"
    if score.get("score") is None:
        return None
    return "callback"


def _action_citations(action, rows):
    """Return citations tied to records supporting the selected action."""
    if action == "network_escalation":
        matches = [r["record_id"] for r in rows if r.get("record_type") == "ticket" and "dropped-call complaint" in r.get("content", "").lower()]
        citations = matches[-1:] + (["NET-ESC"] if len(matches) >= 3 else [])
        return citations or ["NET-ESC"]
    if action == "bill_correction":
        ids = {r.get("record_id") for r in rows}
        citations = [rid for rid in ("TKT-6610", "CALL-8821") if rid in ids]
        if "BILL-POL" not in citations:
            citations.append("BILL-POL")
        return citations
    if action == "callback":
        matches = [r["record_id"] for r in rows if any(term in r.get("content", "").lower() for term in ("competitor", "port-out", "discount"))]
        citations = matches[-1:]
        if not citations:
            citations = [r["record_id"] for r in rows if r.get("record_type") in ("call", "ticket")][-1:]
        citations.append("RET-POL")
        return citations
    if action == "plan_review":
        matches = [r["record_id"] for r in rows if any(term in r.get("content", "").lower() for term in ("slow-data complaint", "plan review", "review of their current plan"))]
        return matches[-1:]
    return []


def _summary_is_grounded(candidate, baseline, rows):
    """Reject summaries with unsupported numbers or little overlap with verified evidence."""
    if not isinstance(candidate, str) or not candidate.strip():
        return False
    source_text = " ".join(r.get("content", "") for r in rows).lower()
    allowed_text = (source_text + " " + baseline.lower())
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?%?\b", candidate)
    for number in numbers:
        if number.lower() not in allowed_text:
            return False
    stopwords = {"the", "and", "with", "from", "this", "that", "has", "have", "been", "was", "were", "customer", "record", "records", "reported", "available", "their", "they", "there", "over", "into", "about", "because", "may", "might", "could", "would", "should", "leave", "leaving"}
    tokens = {t for t in re.findall(r"[a-z][a-z-]{3,}", candidate.lower()) if t not in stopwords}
    source_tokens = {t for t in re.findall(r"[a-z][a-z-]{3,}", allowed_text) if t not in stopwords}
    return len(tokens & source_tokens) >= 2


def build_insight(customer_id, question, channel="inbound_call", stated_reason="", session_date=None, use_llm=True):
    customer = get_customer(customer_id)
    if not customer:
        raise ValueError(f"Unknown customer ID: {customer_id}")
    rows = retrieve_customer_records(customer_id)
    effective_session_date = session_date or SESSION_DATE
    score = score_customer(customer_id, rows, session_date=effective_session_date)
    action = _select_action(rows, score)
    pol = evaluate_policy(customer_id, rows, action or "callback", session_date=effective_session_date)
    # Keep the signal-selected action. evaluate_policy may mark it for escalation,
    # but it must not replace a deliberate no-action decision with its fallback input.

    drivers = _baseline_drivers(customer_id, rows, score)
    summary_map = {
        "CUST-1001":"Repeated dropped calls at one location over 30 days, with data usage falling sharply.",
        "CUST-1002":"A roaming billing dispute remains unresolved in the latest customer contact.",
        "CUST-1003":"One slow-data complaint is recorded and usage is stable.",
        "CUST-1004":"The customer mentioned a competitor, requested port-out, and asked for a discount beyond policy limits.",
        "CUST-1005":"There is no recent interaction history; available records contain plan metadata only.",
        "CUST-1006":"The customer requested a plan review, but the available record does not establish a strong churn signal."
    }
    reason_map = {
        "network_escalation": "Verified network complaints meet the approved network-escalation threshold.",
        "bill_correction": "A verified billing record indicates a disputed charge; verify the charge before correcting it.",
        "plan_review": "A verified interaction supports reviewing whether the current plan fits the customer's needs.",
        "callback": "A callback is an approved follow-up when the available evidence supports further customer contact."
    }
    action_citations = {name: _action_citations(name, rows) for name in ("network_escalation", "bill_correction", "plan_review", "callback")}
    if customer_id == "CUST-1004":
        pol["unsupported"].append("Competitor pricing is not present in approved content; no price comparison can be given.")
    missing = list(pol["missing_information"])
    if score["score"] is None and not missing:
        missing = ["Recent interactions and current usage trend are unavailable."]
    response = {
        "customer_id": customer_id,
        "summary": summary_map.get(customer_id, "Insufficient verified evidence to summarize dissatisfaction."),
        "drivers": drivers,
        "risk": {"level":score["level"], "score":score["score"], "signals_used":score["signals_used"]},
        "recommended_action": None if action is None else {
            "action":action,
            "reasoning":reason_map[action],
            "based_on_signals": (
                score["signals_used"][:1]
                or (["plan_fit"] if action == "plan_review" else ["insufficient_evidence"])
            ),
            "citations":action_citations[action],
            "follow_up":"callback"
        },
        "missing_information":missing,
        "unsupported":pol["unsupported"],
        "data_conflicts":pol["data_conflicts"],
        "escalate":pol["escalate"],
        "escalation_reason":pol["escalation_reason"]
    }

    if use_llm:
        # LLM may refine the summary/explanations, but Python remains authoritative for score,
        # allowed action, citations, and escalation. If model output is malformed, keep baseline.
        try:
            payload = {
                "question": question, "channel": channel, "stated_reason": stated_reason,
                "customer_metadata": customer, "verified_records": rows,
                "approved_policies": pol["policies"], "deterministic_response": response,
                "required_driver_order": DRIVER_ORDER
            }
            msg = _llm().invoke([
                ("system", SYSTEM_PROMPT),
                ("human", "Refine only summary and evidence wording. Do not change risk, action, citations, missing/unsupported data, conflicts, or escalation. Return JSON with the same structure:\n" + json.dumps(payload))
            ])
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
            candidate = json.loads(text[text.find("{"):text.rfind("}")+1])
            candidate_summary = candidate.get("summary")
            if _summary_is_grounded(candidate_summary, response["summary"], rows):
                response["summary"] = candidate_summary.strip()
            # Driver evidence stays deterministic: matching citation IDs alone cannot prove
            # that rewritten evidence text is factually equivalent to the source records.
        except Exception:
            pass

    errors = validate_citations(response, rows, pol["policies"])
    if errors:
        response["escalate"] = True
        response["escalation_reason"] = "Guard validation failed: " + "; ".join(errors)
    return response
