from churn_assistant.agent import build_insight

def test_policy_exception_escalates():
    result = build_insight("CUST-1004", "Customer wants 50% off for 6 months", use_llm=False)
    assert result["escalate"] is True
    assert result["escalation_reason"]
    assert "exceeds" in result["escalation_reason"]

def test_expired_offer_not_available():
    result = build_insight("CUST-1003", "Can I give the festive offer?", use_llm=False)
    assert any("expired" in x.lower() for x in result["unsupported"])
