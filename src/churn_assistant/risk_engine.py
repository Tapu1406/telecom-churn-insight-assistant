from datetime import date, timedelta

from .config import SESSION_DATE
from .repository import retrieve_customer_records

DRIVER_ORDER = [
    "network_quality",
    "billing_dispute",
    "plan_fit",
    "service_experience",
    "competitor_intent",
    "usage_decline",
]

WEIGHTS = {
    "network_complaints_3plus": 3,
    "open_or_disputed_billing": 3,
    "competitor_or_portout": 3,
    "usage_drop_30pct": 2,
    "repeat_contact": 1,
}


def _as_date(value) -> date:
    """Accept date objects or ISO dates, defaulting to the configured session date."""
    if value is None:
        return SESSION_DATE
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def score_customer(customer_id: str, all_records=None, session_date=None):
    """Score verified customer signals using a deterministic 30-day session window."""
    session_day = _as_date(session_date)
    window_start = session_day - timedelta(days=30)
    rows = all_records if all_records is not None else retrieve_customer_records(customer_id)
    rows = [
        r for r in rows
        if r.get("customer_id") == customer_id and r.get("verified") is True
    ]

    dated_rows = []
    for row in rows:
        try:
            row_day = date.fromisoformat(row["date"])
        except (KeyError, TypeError, ValueError):
            # Undated or malformed records cannot contribute to a time-bounded score.
            continue
        if window_start <= row_day <= session_day:
            dated_rows.append(row)

    network = [
        r for r in dated_rows
        if r.get("record_type") == "ticket"
        and "dropped-call complaint" in r.get("content", "").lower()
    ]
    billing_open = any(
        r.get("record_type") in ("call", "ticket")
        and any(term in r.get("content", "").lower() for term in ("still on the bill", "disputed", "double charge"))
        for r in dated_rows
    )
    competitor = any(
        any(term in r.get("content", "").lower() for term in ("competitor", "port-out"))
        for r in dated_rows
    )
    usage_drop = any(
        any(term in r.get("content", "").lower() for term in ("down 35%", "down more than 30%"))
        for r in dated_rows
    )
    contact_rows = [r for r in dated_rows if r.get("record_type") in ("call", "ticket")]
    repeat_contact = len(contact_rows) >= 2 and (bool(network) or billing_open)

    flags = {
        "network_complaints_3plus": len(network) >= 3,
        "open_or_disputed_billing": billing_open,
        "competitor_or_portout": competitor,
        "usage_drop_30pct": usage_drop,
        "repeat_contact": repeat_contact,
    }
    signals = [name for name in WEIGHTS if flags[name]]

    # Metadata-only customers have no interaction evidence, so do not assign a zero risk.
    interaction_rows = [r for r in dated_rows if r.get("record_type") != "metadata"]
    if not interaction_rows:
        return {"score": None, "level": None, "signals_used": [], "signal_flags": flags}

    score = sum(WEIGHTS[name] for name in signals)
    level = "low" if score <= 2 else "medium" if score <= 5 else "high"
    return {"score": score, "level": level, "signals_used": signals, "signal_flags": flags}
