from app.llm_client import call_llm
from app.schemas import FlaggedPattern, InvestigationGraph

SYSTEM_PROMPT = (
    "You write a one-paragraph executive summary for an AML investigation report, "
    "aimed at a compliance officer skimming the case before reading details. "
    "Summarize how many patterns were confirmed, the pattern types, the total accounts "
    "and amount involved, and the highest risk score. 2-4 sentences, no jargon, do not "
    "invent figures not present in the input. Respond with strict JSON only: "
    '{"summary": "..."}'
)


def _fallback_summary(patterns: list[FlaggedPattern], total_amount: float) -> str:
    if not patterns:
        return "No suspicious patterns were confirmed in this investigation."

    pattern_types = ", ".join(sorted({p.pattern_type.replace("_", " ") for p in patterns}))
    accounts = {account for p in patterns for account in p.accounts_involved}
    highest = max(patterns, key=lambda p: p.risk_score)

    return (
        f"This investigation identified {len(patterns)} confirmed pattern(s) "
        f"({pattern_types}) involving {len(accounts)} accounts and "
        f"{total_amount:,.0f} in flagged transfers. The highest-risk finding scored "
        f"{highest.risk_score} ({highest.confidence} confidence) and warrants priority review."
    )


async def generate_executive_summary(graph: InvestigationGraph, patterns: list[FlaggedPattern]) -> str:
    if not patterns:
        return _fallback_summary(patterns, 0)

    involved = {account for p in patterns for account in p.accounts_involved}
    total_amount = sum(
        t.amount for t in graph.transactions if t.from_account in involved and t.to_account in involved
    )

    payload = {
        "pattern_count": len(patterns),
        "pattern_types": sorted({p.pattern_type for p in patterns}),
        "account_count": len(involved),
        "total_amount": total_amount,
        "highest_risk_score": max(p.risk_score for p in patterns),
        "patterns": [
            {
                "pattern_type": p.pattern_type,
                "risk_score": p.risk_score,
                "confidence": p.confidence,
                "accounts_involved": len(p.accounts_involved),
            }
            for p in patterns
        ],
    }

    try:
        result = await call_llm(SYSTEM_PROMPT, f"investigation: {payload}")
        return result.get("summary") or _fallback_summary(patterns, total_amount)
    except Exception:
        return _fallback_summary(patterns, total_amount)
