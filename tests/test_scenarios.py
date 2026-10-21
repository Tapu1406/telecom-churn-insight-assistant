import pytest
from churn_assistant.agent import build_insight

def test_t1_happy_path():
    r = build_insight("CUST-1001", "Why might this customer leave?", use_llm=False)
    assert r["risk"]["level"] == "high"
    assert {d["driver"] for d in r["drivers"]} == {"network_quality", "usage_decline"}
    assert r["recommended_action"]["action"] == "network_escalation"

def test_t2_unknown_customer():
    with pytest.raises(ValueError):
        build_insight("CUST-9999", "Analyze", use_llm=False)

def test_t3_unverified_content():
    r = build_insight("CUST-1001", "Analyze", use_llm=False)
    assert "NOTE-77" not in str(r)

def test_t4_conflicting_billing():
    r = build_insight("CUST-1002", "Billing complaint", use_llm=False)
    assert any("TKT-6610" in c and "CALL-8821" in c for c in r["data_conflicts"])
    assert r["recommended_action"]["action"] == "bill_correction"
    assert r["escalate"] is True

def test_t5_unsupported_competitor_pricing():
    r = build_insight("CUST-1004", "Is the competitor plan cheaper?", use_llm=False)
    assert any("competitor pricing" in x.lower() for x in r["unsupported"]) or any("pricing" in x.lower() for x in r["unsupported"])

def test_t6_expired_offer():
    r = build_insight("CUST-1003", "Can I give the festive offer?", use_llm=False)
    assert any("expired" in x.lower() for x in r["unsupported"])

def test_t7_policy_exception():
    r = build_insight("CUST-1004", "Customer wants 50% off for 6 months", use_llm=False)
    assert r["escalate"] is True
    assert r["escalation_reason"]

def test_t8_sparse_history():
    r = build_insight("CUST-1005", "Analyze", use_llm=False)
    assert r["risk"]["score"] is None
    assert r["risk"]["level"] is None
    assert r["drivers"] == []
    assert r["missing_information"]


def test_llm_summary_with_unsupported_number_is_rejected():
    from churn_assistant.agent import _summary_is_grounded

    rows = [{"content": "Customer contacted support about dropped-call complaints."}]
    assert not _summary_is_grounded(
        "Network repair will take 14 days.",
        "Repeated dropped-call complaints were reported.",
        rows,
    )


def test_recommendation_is_selected_from_verified_signals_not_customer_id():
    from churn_assistant.agent import _select_action

    rows = [
        {
            "customer_id": "CUST-OTHER",
            "record_type": "ticket",
            "record_id": "TKT-X",
            "date": "2026-10-01",
            "verified": True,
            "content": "Dropped-call complaint from the same cell/location.",
        },
        {
            "customer_id": "CUST-OTHER",
            "record_type": "ticket",
            "record_id": "TKT-Y",
            "date": "2026-10-02",
            "verified": True,
            "content": "Dropped-call complaint from the same cell/location.",
        },
        {
            "customer_id": "CUST-OTHER",
            "record_type": "ticket",
            "record_id": "TKT-Z",
            "date": "2026-10-03",
            "verified": True,
            "content": "Dropped-call complaint from the same cell/location.",
        },
    ]
    score = {
        "signal_flags": {
            "network_complaints_3plus": True,
            "open_or_disputed_billing": False,
            "competitor_or_portout": False,
        },
        "score": 3,
    }
    assert _select_action(rows, score) == "network_escalation"
