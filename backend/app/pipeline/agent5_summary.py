from app.schemas import FlaggedPattern, InvestigationGraph


def _fallback_summary(patterns: list[FlaggedPattern], total_amount: float) -> str:
    if not patterns:
        return "No suspicious patterns were confirmed in this investigation."

    pattern_types = ", ".join(sorted({p.pattern_type.replace("_", " ") for p in patterns}))
    accounts = {account for p in patterns for account in p.accounts_involved}
    highest = max(patterns, key=lambda p: p.risk_score)

    return (
        f"This investigation identified {len(patterns)} confirmed pattern(s) "
        f"({pattern_types}) involving {len(accounts)} accounts and "
        f"Rs. {total_amount:,.0f} in flagged transfers. The highest-risk finding scored "
        f"{highest.risk_score} ({highest.confidence} confidence) and warrants priority review."
    )


async def generate_executive_summary(graph: InvestigationGraph, patterns: list[FlaggedPattern]) -> str:
    # Risk scoring already ran one LLM call per pattern with the narrative -
    # this summary is just a deterministic roll-up of numbers the pipeline
    # already computed, so it skips a 4th sequential LLM round-trip per run.
    if not patterns:
        return _fallback_summary(patterns, 0)

    involved = {account for p in patterns for account in p.accounts_involved}
    total_amount = sum(
        t.amount for t in graph.transactions if t.from_account in involved and t.to_account in involved
    )
    return _fallback_summary(patterns, total_amount)
