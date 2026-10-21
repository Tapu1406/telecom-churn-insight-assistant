# Telecom Customer Churn Insight Assistant

An evidence-grounded assistant for telecom service agents. It summarizes verified customer records, calculates churn risk with deterministic Python rules, recommends one action from a fixed catalog, validates citations and policy constraints, and pauses for supervisor review when required.

## Technology

- Python 3.12+
- `uv`
- LangGraph
- Ollama: `gpt-oss:120b-cloud`
- Streamlit
- JSON sample records and policy documents
- pytest

## Setup

1. Install Python 3.12+ and `uv`.
2. Ensure Ollama is installed/configured and the specified model is available.
3. Copy `.env.example` to `.env` and adjust only the runtime connection settings if necessary.
4. From the project root:

   ```bash
   uv sync --extra dev
   uv run streamlit run app.py
   ```

5. Run tests:

   ```bash
   uv run pytest
   ```

Optional API installation and start:

```bash
uv sync --extra api --extra dev
uv run uvicorn churn_assistant.api:app --app-dir src --reload
```

The API exposes `POST /insight`.

## Workflow

Request -> input/customer validation -> retrieve records and policy -> deterministic risk scoring -> LLM-generated structured explanation -> guard checks -> escalation decision -> response or supervisor interruption.

The graph's supervisor node uses LangGraph's `interrupt()` and a checkpointer. In this sample app, an escalation is surfaced as pending supervisor review. A production supervisor UI would resume the graph with `Command(resume=...)`.

## Data and verification assumptions

- The dataset is fictional and contains no customer names or phone numbers.
- Only records with `verified: true` can be used as evidence, citations, or risk signals.
- Customer IDs must exist in `data/customers.json`.
- All citations must match records retrieved for that request or approved policy documents.
- The latest dated record determines the current reported status when two records conflict. Both sides of a material conflict are surfaced. A later complaint is not treated as proof that a correction has occurred.
- The risk score is computed in Python from verified records dated within the 30-day window ending on `SESSION_DATE`. Records after the session date, older than the window, unverified, or missing a usable date do not contribute to time-bounded signals. The LLM cannot change the score or band.
- When there are no qualifying signals, the risk score and level are `null`, and `missing_information` must not be empty.
- The assistant cannot know competitor pricing or network repair dates because those facts are not present in the approved dataset.
- The retention action is selected from verified signal flags and observed interaction content, not from the customer ID. Citations for the selected action are assembled from the supporting record(s) and applicable policy document.
- LLM-written summaries are accepted only if they pass a conservative grounding check against verified source text and the deterministic baseline. Driver evidence remains deterministic; citation-ID agreement alone is not treated as proof that rewritten evidence is accurate. The grounding check is a safeguard, not a substitute for a human audit.
- The session date defaults to `2026-10-15` for deterministic expired-offer testing. Change it explicitly when testing a different session date.

## Risk scoring

| Signal | Weight |
|---|---:|
| 3+ network complaints in 30 days | +3 |
| Open or disputed billing issue | +3 |
| Competitor mention or port-out request | +3 |
| Usage down >30% month on month | +2 |
| Repeat contact for the same issue | +1 |

Bands: 0–2 low, 3–5 medium, 6+ high.

The risk engine checks the actual verified records and uses fixed rules. Unverified records are excluded before scoring.

## Retention catalog

- `plan_review`
- `network_escalation`
- `bill_correction`
- `callback`

The policy permits a bill credit up to Rs 500 or a plan discount up to 20% for 3 months. Anything above those limits is escalated. Expired offers are never presented as available. A network escalation requires 3 or more coverage complaints from one location in 30 days.

## Escalation

The guard layer escalates policy exceptions, unresolved material conflicts, and citation/validation failures. The LangGraph supervisor node calls `interrupt()` so the graph pauses for a human decision. An escalation response includes a non-empty `escalation_reason`.

## Driver order

Drivers are emitted in this fixed order:
1. `network_quality`
2. `billing_dispute`
3. `plan_fit`
4. `service_experience`
5. `competitor_intent`
6. `usage_decline`

## Tests

`tests/` covers risk scoring, 30-day window enforcement, exclusion of unverified records, verified citations, policy limits, conflict handling, summary-grounding safeguards, signal-based action selection, and the T1–T8 scenarios. The tests use deterministic rules and do not require a live LLM connection.

## Limitations

This is a fictional learning PoC, not a production telecom system. It has no live CRM integration, real billing correction, network diagnostics, or actual customer-offer execution. It must not promise that a repair date, competitor price, or unavailable policy exception exists.

## Review hardening changes

- Risk scoring now uses the configured `SESSION_DATE` and excludes records outside the inclusive 30-day window, records dated after the session, malformed dates, and unverified records.
- The approved action is selected from verified signal flags and interaction content instead of a customer-ID switch statement.
- Action citations are assembled from relevant verified interaction records and applicable policy documents.
- Model-written summaries are checked for unsupported numeric claims and evidence overlap before acceptance; deterministic summaries remain the fallback. Driver evidence remains deterministic.
- Regression tests cover records outside the 30-day window, unverified records, signal-based action selection, and rejection of an unsupported numeric summary.
