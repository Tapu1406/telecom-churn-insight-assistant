from churn_assistant.agent import build_insight
from churn_assistant.repository import retrieve_customer_records, retrieve_policies
from churn_assistant.citation_validator import validate_citations
from churn_assistant.config import SESSION_DATE

def test_unverified_note_never_cited():
    result = build_insight("CUST-1001", "Why leave?", use_llm=False)
    all_citations = [c for d in result["drivers"] for c in d["citations"]]
    assert "NOTE-77" not in all_citations
    assert all("NOTE-77" not in c for c in all_citations)

def test_all_citations_resolve():
    result = build_insight("CUST-1001", "Why leave?", use_llm=False)
    errors = validate_citations(result, retrieve_customer_records("CUST-1001"), retrieve_policies(SESSION_DATE))
    assert errors == []
