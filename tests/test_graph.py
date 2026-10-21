
from uuid import uuid4

from langgraph.types import Command
from churn_assistant.graph import graph


def start_escalation_review(customer_id, thread_id):
    """Run the graph until supervisor review is required."""
    result = graph.invoke(
        {
            "customer_id": customer_id,
            "question": "Why might this customer leave?",
            "channel": "inbound_call",
            "stated_reason": "Billing complaint",
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    assert result["response"].get("escalate") is True
    return result


def test_supervisor_approval():
    thread_id = f"test-approval-{uuid4()}"

    start_escalation_review("CUST-1002", thread_id)

    result = graph.invoke(
        Command(resume={"approved": True}),
        config={"configurable": {"thread_id": thread_id}},
    )

    response = result["response"]
    assert response["escalate"] is False
    assert response["escalation_reason"] is None


def test_supervisor_rejection():
    thread_id = f"test-rejection-{uuid4()}"

    start_escalation_review("CUST-1002", thread_id)

    result = graph.invoke(
        Command(resume={"approved": False}),
        config={"configurable": {"thread_id": thread_id}},
    )

    response = result["response"]
    assert response["escalate"] is True
    assert "Supervisor rejected" in response["summary"]
