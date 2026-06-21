from typing import Literal, Optional

from pydantic import BaseModel

# The four named detectors emit one of these, but the general anomaly detector
# (app/pipeline/anomaly.py) can mint its own free-form snake_case label for a scam
# shape none of them cover - so this is a plain str, not a closed Literal.
PatternType = str
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
    watchlist_note: Optional[str] = None


class FlaggedPattern(BaseModel):
    pattern_type: PatternType
    accounts_involved: list[str]
    risk_score: int = 0
    confidence: Confidence = "low"
    contributing_factors: list[str] = []
    reasoning: str = ""
    narrative: str = ""
    additional_notes: Optional[str] = None
    skeptic_challenge: Optional[str] = None
    review_verdict: Optional[str] = None
    next_steps: list[str] = []
    similar_past_cases: list[str] = []


class InvestigationGraph(BaseModel):
    scenario_id: str
    accounts: list[Account]
    transactions: list[Transaction]
    flagged_patterns: list[FlaggedPattern] = []
    executive_summary: Optional[str] = None


class PipelineEvent(BaseModel):
    stage: str
    status: StageStatus
    data: Optional[dict] = None


class ScenarioMeta(BaseModel):
    id: str
    name: str
    description: str
    transaction_count: int
    deletable: bool = False


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    answer: str


class AuditEntry(BaseModel):
    id: str
    type: Literal["investigation_run", "chat_message"]
    scenario_id: str
    timestamp: str
    summary: str
    details: dict
