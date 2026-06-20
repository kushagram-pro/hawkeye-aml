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


async def generate_narratives(graph: InvestigationGraph, patterns: list[FlaggedPattern]) -> list[FlaggedPattern]:
    # Agent 3 (scoring) already produces the narrative in the same LLM call as the
    # risk score, so this stage only needs to backfill the rare case where that
    # call returned no narrative at all - keeps the 4-stage timeline without a
    # second round-trip to the LLM.
    for pattern in patterns:
        if not pattern.narrative:
            pattern.narrative = _fallback_narrative(pattern, _pattern_transactions(pattern, graph.transactions))

    return patterns
