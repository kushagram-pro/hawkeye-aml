from app.llm_client import call_llm
from app.schemas import FlaggedPattern, InvestigationGraph, Transaction

SYSTEM_PROMPT = (
    "You are an AML investigator writing a plain-language explanation of a flagged "
    "money-laundering pattern for a fraud analyst who has not seen the raw data. "
    "Write 2-4 sentences, concrete (cite account ids, amounts, timeframes), no jargon "
    "beyond naming the pattern type once. Respond with strict JSON: "
    '{"narrative": "..."}'
)


def _pattern_transactions(pattern: FlaggedPattern, all_transactions: list[Transaction]) -> list[Transaction]:
    involved = set(pattern.accounts_involved)
    return [t for t in all_transactions if t.from_account in involved and t.to_account in involved]


def _fallback_narrative(pattern: FlaggedPattern, txs: list[Transaction]) -> str:
    total = sum(t.amount for t in txs)
    accounts = ", ".join(pattern.accounts_involved)
    return (
        f"A {pattern.pattern_type.replace('_', ' ')} pattern was detected involving "
        f"{len(pattern.accounts_involved)} accounts ({accounts}) across {len(txs)} transactions "
        f"totaling {total:,.0f}. {pattern.reasoning}"
    ).strip()


async def generate_narratives(graph: InvestigationGraph, patterns: list[FlaggedPattern]) -> list[FlaggedPattern]:
    for pattern in patterns:
        txs = _pattern_transactions(pattern, graph.transactions)
        user_prompt = (
            f"pattern_type: {pattern.pattern_type}\n"
            f"accounts_involved: {pattern.accounts_involved}\n"
            f"risk_score: {pattern.risk_score}\n"
            f"confidence: {pattern.confidence}\n"
            f"contributing_factors: {pattern.contributing_factors}\n"
            f"transactions: {[t.model_dump() for t in txs]}"
        )
        try:
            result = await call_llm(SYSTEM_PROMPT, user_prompt)
            pattern.narrative = result.get("narrative", "") or _fallback_narrative(pattern, txs)
        except Exception:
            pattern.narrative = _fallback_narrative(pattern, txs)

    return patterns
