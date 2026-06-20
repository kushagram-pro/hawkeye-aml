from typing import Literal, Optional

from pydantic import BaseModel

PatternType = Literal["structuring", "layering", "mule_network"]
Confidence = Literal["low", "medium", "high"]
StageStatus = Literal["started", "completed", "failed"]


class Transaction(BaseModel):
    from_account: str
    to_account: str
    amount: float
    timestamp: str
    currency: str = "INR"


class Account(BaseModel):
    id: str
    total_in: float = 0
    total_out: float = 0
    transaction_count: int = 0
    unique_counterparties: int = 0
    risk_score: Optional[int] = None
    confidence: Optional[Confidence] = None
    flags: list[str] = []


class FlaggedPattern(BaseModel):
    pattern_type: PatternType
    accounts_involved: list[str]
    risk_score: int = 0
    confidence: Confidence = "low"
    contributing_factors: list[str] = []
    reasoning: str = ""
    narrative: str = ""


class InvestigationGraph(BaseModel):
    scenario_id: str
    accounts: list[Account]
    transactions: list[Transaction]
    flagged_patterns: list[FlaggedPattern] = []


class PipelineEvent(BaseModel):
    stage: str
    status: StageStatus
    data: Optional[dict] = None


class ScenarioMeta(BaseModel):
    id: str
    name: str
    description: str
    transaction_count: int
