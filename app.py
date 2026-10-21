
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import streamlit as st
from langgraph.types import Command
from churn_assistant.graph import graph


# Page configuration
st.set_page_config(
    page_title="Telecom Churn Insight Assistant",
    layout="wide",
)

st.title("Telecom Churn Insight Assistant")
st.caption(
    "Evidence-grounded summaries, deterministic churn risk, "
    "and policy-aware actions."
)

left, right = st.columns(2)

# -------------------------
# Agent request
# -------------------------
with left:
    st.subheader("Agent request")

    customer_id = st.selectbox(
        "Customer ID",
        [f"CUST-{i}" for i in
         ["1001", "1002", "1003", "1004", "1005", "1006"]],
    )

    question = st.text_input(
        "Agent question",
        "Why might this customer leave, and what should I do?",
    )

    channel = st.selectbox(
        "Channel",
        ["inbound_call", "outbound_call", "chat", "email"],
    )

    stated_reason = st.text_area(
        "Customer's stated reason",
        "Calls keep dropping at home"
        if customer_id == "CUST-1001"
        else "",
    )

    analyze = st.button("Analyze", type="primary")


# -------------------------
# Analysis and supervisor review
# -------------------------
with right:
    st.subheader("Analysis")

    if analyze:
        thread_id = str(uuid4())

        try:
            with st.spinner(
                "Checking verified records and policies..."
            ):
                result = graph.invoke(
                    {
                        "customer_id": customer_id,
                        "question": question,
                        "channel": channel,
                        "stated_reason": stated_reason,
                    },
                    config={
                        "configurable": {
                            "thread_id": thread_id
                        }
                    },
                )

            result = result.get("response", result)

            st.session_state["last_result"] = result
            st.session_state["review_thread_id"] = thread_id
            st.session_state["review_pending"] = bool(
                result.get("escalate")
            )

        except Exception as exc:
            st.error(f"Analysis failed: {exc}")

    result = st.session_state.get("last_result")

    if result:
        # Risk
        risk = result["risk"]

        st.metric(
            "Churn risk",
            (risk["level"] or "Unknown").upper(),
            (
                f"Score: {risk['score']}"
                if risk["score"] is not None
                else "Score: N/A"
            ),
        )

        # Recommended action
        if result.get("recommended_action"):
            st.success(
                "Recommended action: "
                + result["recommended_action"]["action"]
            )
            st.write(result["recommended_action"]["reasoning"])

        # Summary
        st.markdown("**Summary**")
        st.write(result["summary"])

        # Drivers and evidence
        st.markdown("**Drivers and evidence**")

        if result["drivers"]:
            st.dataframe(
                [
                    {
                        "Driver": d["driver"],
                        "Evidence": d["evidence"],
                        "Sources": ", ".join(d["citations"]),
                    }
                    for d in result["drivers"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No supported dissatisfaction drivers found.")

        # Missing information
        if result["missing_information"]:
            st.warning(
                "Missing information: "
                + "; ".join(result["missing_information"])
            )

        # Unsupported requests or content
        if result["unsupported"]:
            st.info(
                "Unsupported: "
                + "; ".join(result["unsupported"])
            )

        # Data conflicts
        if result["data_conflicts"]:
            st.warning(
                "Data conflicts: "
                + "; ".join(result["data_conflicts"])
            )

        # Supervisor status
        if result.get("escalate"):
            if "Supervisor rejected" in result.get("summary", ""):
                st.error("Supervisor rejected the proposed action.")
            else:
                st.error(
                    "Supervisor review required: "
                    + (
                        result.get("escalation_reason")
                        or "Reason not provided"
                    )
                )
        else:
            st.success(
                "Supervisor review: not required or approved"
            )

        # Supervisor approval/rejection controls
        if st.session_state.get("review_pending", False):
            st.subheader("Supervisor review")

            st.write("Review the proposed action before deciding.")

            st.json(result.get("recommended_action"))

            col_approve, col_reject = st.columns(2)

            with col_approve:
                if st.button("Approve", type="primary"):
                    try:
                        updated = graph.invoke(
                            Command(resume={"approved": True}),
                            config={
                                "configurable": {
                                    "thread_id": st.session_state[
                                        "review_thread_id"
                                    ]
                                }
                            },
                        )

                        st.session_state["last_result"] = (
                            updated["response"]
                        )
                        st.session_state["review_pending"] = False
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Approval failed: {exc}")

            with col_reject:
                if st.button("Reject"):
                    try:
                        updated = graph.invoke(
                            Command(resume={"approved": False}),
                            config={
                                "configurable": {
                                    "thread_id": st.session_state[
                                        "review_thread_id"
                                    ]
                                }
                            },
                        )

                        st.session_state["last_result"] = (
                            updated["response"]
                        )
                        st.session_state["review_pending"] = False
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Rejection failed: {exc}")

        # Full response
        with st.expander("Structured response JSON"):
            st.json(result)
