from app.schemas import FlaggedPattern, InvestigationGraph, Transaction


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


def _fallback_next_steps(pattern: FlaggedPattern) -> list[str]:
    primary = pattern.accounts_involved[0] if pattern.accounts_involved else "the flagged account"
    return [
        f"Pull KYC and source-of-funds documentation for {primary}.",
        f"Check whether any of {', '.join(pattern.accounts_involved)} appear in prior SAR filings.",
        "Verify counterparty relationships for unusually large or rapid transfers in this cluster.",
    ]


async def generate_narratives(graph: InvestigationGraph, patterns: list[FlaggedPattern]) -> list[FlaggedPattern]:
    # Agent 3 (scoring) already produces the narrative and next_steps in the same
    # LLM call as the risk score, so this stage only needs to backfill the rare
    # case where that call returned nothing - keeps the timeline without a second
    # round-trip to the LLM.
    for pattern in patterns:
        if not pattern.narrative:
            pattern.narrative = _fallback_narrative(pattern, _pattern_transactions(pattern, graph.transactions))
        if not pattern.next_steps:
            pattern.next_steps = _fallback_next_steps(pattern)

    return patterns
