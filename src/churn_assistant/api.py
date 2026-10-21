from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .agent import build_insight

app = FastAPI(title="Telecom Churn Insight Assistant")

class InsightRequest(BaseModel):
    customer_id: str
    question: str
    context: dict = {}

@app.post("/insight")
def insight(req: InsightRequest):
    try:
        return build_insight(
            req.customer_id,
            req.question,
            req.context.get("channel", "inbound_call"),
            req.context.get("stated_reason", "")
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
