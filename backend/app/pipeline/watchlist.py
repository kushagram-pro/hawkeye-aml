"""Repeat-offender watchlist.

A sanctions or PEP screen checks incoming entities against an externally
maintained list of known-bad actors. This platform has no real identity data
to screen (accounts are bare IDs, no KYC), but it does accumulate its own
case history via `pattern_memory` - so this module screens every account in
the current investigation against accounts that were part of a high-risk
confirmed pattern in ANY past investigation. It runs immediately after
ingestion, before any rule or LLM pass has looked at this scenario's
transactions, so a repeat offender gets flagged even if this run's data alone
wouldn't have tripped a detector.
"""

from app.pipeline import pattern_memory
from app.schemas import InvestigationGraph

HIGH_RISK_THRESHOLD = 80


def screen(scenario_id: str, graph: InvestigationGraph) -> dict[str, str]:
    account_ids = {account.id for account in graph.accounts}
    records = [
        record
        for record in pattern_memory.all_records()
        if record["scenario_id"] != scenario_id and record["risk_score"] >= HIGH_RISK_THRESHOLD
    ]

    hits: dict[str, str] = {}
    for record in records:
        for account_id in record["accounts_involved"]:
            if account_id in account_ids and account_id not in hits:
                hits[account_id] = (
                    f"Flagged in a prior {record['pattern_type'].replace('_', ' ')} case "
                    f"from scenario '{record['scenario_id']}' (risk {record['risk_score']}, "
                    f"{record['confidence']} confidence)."
                )

    return hits
