from churn_assistant.risk_engine import score_customer

def test_cust_1001_is_high_risk_score_6():
    result = score_customer("CUST-1001")
    assert result["score"] == 6
    assert result["level"] == "high"
    assert result["signals_used"] == [
        "network_complaints_3plus", "usage_drop_30pct", "repeat_contact"
    ]

def test_sparse_history_has_null_risk():
    result = score_customer("CUST-1005")
    assert result["score"] is None
    assert result["level"] is None


def test_records_outside_session_30_day_window_do_not_contribute_to_risk():
    from datetime import date
    from churn_assistant.risk_engine import score_customer

    rows = [
        {
            "customer_id": "CUST-X",
            "record_type": "ticket",
            "record_id": f"TKT-{i}",
            "date": "2026-09-01",
            "verified": True,
            "content": "Dropped-call complaint from the same cell/location.",
        }
        for i in range(3)
    ]
    result = score_customer("CUST-X", rows, session_date=date(2026, 10, 15))
    assert result["score"] is None
    assert result["level"] is None
    assert result["signals_used"] == []


def test_unverified_records_never_contribute_to_risk():
    rows = [
        {
            "customer_id": "CUST-X",
            "record_type": "ticket",
            "record_id": f"TKT-{i}",
            "date": "2026-10-01",
            "verified": False,
            "content": "Dropped-call complaint from the same cell/location.",
        }
        for i in range(3)
    ]
    result = score_customer("CUST-X", rows, session_date="2026-10-15")
    assert result["score"] is None
    assert result["signals_used"] == []
