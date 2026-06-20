import asyncio
import statistics
from datetime import datetime

from app.llm_client import call_llm
from app.schemas import Account, FlaggedPattern, InvestigationGraph, Transaction

SYSTEM_PROMPT = (
    "You are a risk-scoring and case-writing AI for an AML investigation platform. "
    "You will be given a CONFIRMED suspicious pattern with the analyst's reasoning and "
    "its underlying risk factors. Do two things in one pass: "
    "1. Assign a risk_score (0-100) and confidence level based on severity, not just "
    "pattern type - a structuring pattern involving 20 accounts and a large sum is "
    "higher risk than one involving 4 accounts and a small sum. "
    "2. Write a 2-4 sentence plain-language narrative explaining what happened and why "
    "it's suspicious, in the style of an experienced fraud investigator's case note. Be "
    "specific about amounts, account counts, and timing where available. Do not invent "
    "details not present in the input. "
    "Respond with strict JSON only: "
    '{"risk_score": <int 0-100>, "confidence": "low"|"medium"|"high", '
    '"contributing_factors": ["factor: explanation", ...], "narrative": "2-4 sentences"}'
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


def _fallback_narrative(pattern: FlaggedPattern, txs: list[Transaction]) -> str:
    total = sum(t.amount for t in txs)
    accounts = ", ".join(pattern.accounts_involved)
    return (
        f"A {pattern.pattern_type.replace('_', ' ')} pattern was detected involving "
        f"{len(pattern.accounts_involved)} accounts ({accounts}) across {len(txs)} transactions "
        f"totaling {total:,.0f}. {pattern.reasoning}"
    ).strip()


def _fallback_score_and_narrative(pattern: FlaggedPattern, factors: dict, txs: list[Transaction]) -> dict:
    score = min(100, int(factors["network_density"] * 8 + factors["velocity_tx_per_hour"] * 10 + 20))
    confidence = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return {
        "risk_score": score,
        "confidence": confidence,
        "contributing_factors": [
            f"network_density: {factors['network_density']} accounts involved",
            f"velocity: {factors['velocity_tx_per_hour']} tx/hour",
        ],
        "narrative": _fallback_narrative(pattern, txs),
    }


async def _score_and_narrate_one(
    pattern: FlaggedPattern, txs: list[Transaction], accounts_index: dict[str, Account]
) -> dict:
    factors = _compute_factors(pattern, txs, accounts_index)
    try:
        result = await call_llm(SYSTEM_PROMPT, f"risk_factors: {factors}")
        if not result.get("narrative"):
            result["narrative"] = _fallback_narrative(pattern, txs)
        return result
    except Exception:
        return _fallback_score_and_narrative(pattern, factors, txs)


async def score_patterns(graph: InvestigationGraph, patterns: list[FlaggedPattern]) -> list[FlaggedPattern]:
    accounts_index = {a.id: a for a in graph.accounts}

    if not patterns:
        return patterns

    pattern_txs = [_pattern_transactions(pattern, graph.transactions) for pattern in patterns]
    results = await asyncio.gather(
        *(_score_and_narrate_one(pattern, txs, accounts_index) for pattern, txs in zip(patterns, pattern_txs))
    )

    for pattern, result in zip(patterns, results):
        pattern.risk_score = int(result.get("risk_score", 0))
        pattern.confidence = result.get("confidence", "low")
        pattern.contributing_factors = result.get("contributing_factors", [])
        pattern.narrative = result.get("narrative", "")

        for account_id in pattern.accounts_involved:
            account = accounts_index.get(account_id)
            if account and (account.risk_score is None or pattern.risk_score > account.risk_score):
                account.risk_score = pattern.risk_score
                account.confidence = pattern.confidence
            if account and pattern.pattern_type not in account.flags:
                account.flags.append(pattern.pattern_type)

    patterns.sort(key=lambda p: p.risk_score, reverse=True)
    return patterns
