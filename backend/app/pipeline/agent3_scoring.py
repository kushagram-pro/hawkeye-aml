import statistics
from datetime import datetime

from app.llm_client import call_llm
from app.schemas import Account, FlaggedPattern, InvestigationGraph, Transaction

SYSTEM_PROMPT = (
    "You are an AML risk-scoring engine. Given a confirmed suspicious pattern and its "
    "underlying risk factors, assign a risk_score from 0-100 and a confidence level. "
    "Respond with strict JSON: "
    '{"risk_score": <int 0-100>, "confidence": "low"|"medium"|"high", '
    '"contributing_factors": ["factor: explanation", ...]}'
)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _pattern_transactions(pattern: FlaggedPattern, all_transactions: list[Transaction]) -> list[Transaction]:
    involved = set(pattern.accounts_involved)
    return [t for t in all_transactions if t.from_account in involved and t.to_account in involved]


def _compute_factors(pattern: FlaggedPattern, txs: list[Transaction], accounts_index: dict[str, Account]) -> dict:
    total_amount = sum(t.amount for t in txs)
    timestamps = sorted(_parse(t.timestamp) for t in txs)
    span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600 if len(timestamps) > 1 else 0
    velocity = len(txs) / span_hours if span_hours > 0 else len(txs)

    if len(timestamps) > 1:
        deltas = [
            (timestamps[i + 1] - timestamps[i]).total_seconds() for i in range(len(timestamps) - 1)
        ]
        time_clustering = 1 / (1 + statistics.pstdev(deltas) / 3600) if deltas else 1.0
    else:
        time_clustering = 1.0

    network_density = len(pattern.accounts_involved)

    return {
        "pattern_type": pattern.pattern_type,
        "accounts_involved": pattern.accounts_involved,
        "total_amount_moved": total_amount,
        "transaction_count": len(txs),
        "velocity_tx_per_hour": round(velocity, 3),
        "time_clustering_score": round(time_clustering, 3),
        "network_density": network_density,
        "reasoning_from_detection": pattern.reasoning,
    }


def _fallback_score(factors: dict) -> dict:
    score = min(100, int(factors["network_density"] * 8 + factors["velocity_tx_per_hour"] * 10 + 20))
    confidence = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return {
        "risk_score": score,
        "confidence": confidence,
        "contributing_factors": [
            f"network_density: {factors['network_density']} accounts involved",
            f"velocity: {factors['velocity_tx_per_hour']} tx/hour",
        ],
    }


async def score_patterns(graph: InvestigationGraph, patterns: list[FlaggedPattern]) -> list[FlaggedPattern]:
    accounts_index = {a.id: a for a in graph.accounts}

    for pattern in patterns:
        txs = _pattern_transactions(pattern, graph.transactions)
        factors = _compute_factors(pattern, txs, accounts_index)
        try:
            result = await call_llm(SYSTEM_PROMPT, f"risk_factors: {factors}")
        except Exception:
            result = _fallback_score(factors)

        pattern.risk_score = int(result.get("risk_score", 0))
        pattern.confidence = result.get("confidence", "low")
        pattern.contributing_factors = result.get("contributing_factors", [])

        for account_id in pattern.accounts_involved:
            account = accounts_index.get(account_id)
            if account and (account.risk_score is None or pattern.risk_score > account.risk_score):
                account.risk_score = pattern.risk_score
                account.confidence = pattern.confidence
            if account and pattern.pattern_type not in account.flags:
                account.flags.append(pattern.pattern_type)

    patterns.sort(key=lambda p: p.risk_score, reverse=True)
    return patterns
