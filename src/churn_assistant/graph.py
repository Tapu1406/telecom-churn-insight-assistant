from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langgraph.types import Command
from .agent import build_insight

class State(TypedDict, total=False):
    customer_id: str
    question: str
    channel: str
    stated_reason: str
    response: dict[str, Any]
    escalation_decision: dict[str, Any]

def analyze_node(state: State):
    response = build_insight(
        state["customer_id"], state.get("question", ""),
        state.get("channel", "inbound_call"),
        state.get("stated_reason", "")
    )
    return {"response": response}

def escalation_node(state: State):
    response = state["response"]
    if response.get("escalate"):
        decision = interrupt({
            "type": "supervisor_review",
            "customer_id": response["customer_id"],
            "reason": response.get("escalation_reason"),
            "proposed_response": response
        })
        return {"escalation_decision": decision}
    return {"escalation_decision": {"approved": True, "required": False}}

def finalize_node(state: State):
    response = dict(state["response"])
    decision = state.get("escalation_decision", {})
    if response.get("escalate") and decision.get("approved") is True:
        response["escalation_reason"] = None
        response["escalate"] = False
    elif response.get("escalate") and decision.get("approved") is False:
        response["summary"] += " Supervisor rejected the proposed action."
    return {"response": response}

builder = StateGraph(State)
builder.add_node("analyze", analyze_node)
builder.add_node("supervisor_review", escalation_node)
builder.add_node("finalize", finalize_node)
builder.add_edge(START, "analyze")
builder.add_edge("analyze", "supervisor_review")
builder.add_edge("supervisor_review", "finalize")
builder.add_edge("finalize", END)
graph = builder.compile(checkpointer=MemorySaver())
