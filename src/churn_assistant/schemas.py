from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

DriverName = Literal[
    "network_quality", "billing_dispute", "plan_fit",
    "service_experience", "competitor_intent", "usage_decline"
]
ActionName = Literal["plan_review", "network_escalation", "bill_correction", "callback"]

class Driver(BaseModel):
    model_config = ConfigDict(extra="forbid")
    driver: DriverName
    evidence: str
    citations: list[str] = Field(min_length=1)

class Risk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["low", "medium", "high"] | None
    score: int | None
    signals_used: list[str]

class RecommendedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: ActionName
    reasoning: str
    based_on_signals: list[str] = Field(min_length=1)
    citations: list[str] = Field(min_length=1)
    follow_up: str

class InsightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str
    summary: str
    drivers: list[Driver]
    risk: Risk
    recommended_action: RecommendedAction | None
    missing_information: list[str]
    unsupported: list[str]
    data_conflicts: list[str]
    escalate: bool
    escalation_reason: str | None
