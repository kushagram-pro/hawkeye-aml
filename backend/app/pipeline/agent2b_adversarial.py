"""Adversarial second-opinion review.

Agent 2 confirms a candidate pattern against its own reasoning - it never argues
with itself. This module re-examines each already-confirmed pattern through an
independent, deliberately skeptical second LLM pass that is instructed to look
for the false-positive explanation the first pass missed (a payroll run that
looks like structuring, a legitimate aggregator that looks like a mule, etc).
A pattern that survives the challenge gets the challenge text attached for
analyst transparency; a pattern the skeptic genuinely overturns is dropped
from the final flagged list entirely, rather than just being noted.
"""

import asyncio

from app.llm_client import call_llm
from app.schemas import FlaggedPattern, InvestigationGraph, Transaction

SYSTEM_PROMPT = (
    "You are a second, independent financial-crime reviewer auditing a colleague's "
    "pattern confirmation before it goes into a compliance report. You will be given "
    "a candidate pattern_type, the accounts and transactions involved, and the first "
    "analyst's confirmation reasoning. Do not simply rubber-stamp the first analyst - "
    "actively look for the strongest reason this could be a false positive or an "
    "innocent explanation (e.g. payroll, merchant settlement, family transfers, "
    "an aggregator account). "
    "Your prior should be that the first analyst was right: most candidates that "
    "reach you are correctly flagged. Set still_confirmed to false ONLY if you found "
    "a SPECIFIC, concrete innocent explanation that fits the actual data given - "
    "general uncertainty, missing context, or 'cannot conclusively rule out fraud' is "
    "NOT grounds to overturn; in that case still_confirmed must stay true. "
    "still_confirmed must logically match your own challenge text - if your challenge "
    "concludes there is no strong innocent explanation, still_confirmed must be true. "
    "Never invent facts not present in the input. All monetary amounts in this data "
    "are in Indian Rupees - if you cite any amount, write it as 'Rs. <amount>', never "
    "'$' or 'USD'. Respond with strict JSON only: "
    '{"challenge": "2-3 sentences with the strongest counter-argument you can find, '
    'or why none exists", "still_confirmed": true|false}'
)


def _pattern_transactions(pattern: FlaggedPattern, all_transactions: list[Transaction]) -> list[Transaction]:
    involved = set(pattern.accounts_involved)
    return [t for t in all_transactions if t.from_account in involved and t.to_account in involved]


async def _challenge(pattern: FlaggedPattern, txs: list[Transaction]) -> dict:
    user_prompt = (
        f"pattern_type: {pattern.pattern_type}\n"
        f"accounts_involved: {pattern.accounts_involved}\n"
        f"first_analyst_reasoning: {pattern.reasoning}\n"
        f"transactions: {[t.model_dump() for t in txs]}"
    )
    try:
        return await call_llm(SYSTEM_PROMPT, user_prompt)
    except Exception:
        # Review unavailable - fail open and keep the original confirmation rather
        # than silently dropping a pattern an analyst hasn't actually re-examined.
        return {"still_confirmed": True, "challenge": None}


async def run_adversarial_review(
    graph: InvestigationGraph, patterns: list[FlaggedPattern]
) -> tuple[list[FlaggedPattern], int]:
    if not patterns:
        return patterns, 0

    results = await asyncio.gather(
        *(_challenge(pattern, _pattern_transactions(pattern, graph.transactions)) for pattern in patterns)
    )

    surviving: list[FlaggedPattern] = []
    overturned = 0
    for pattern, result in zip(patterns, results):
        if result.get("still_confirmed", True):
            pattern.skeptic_challenge = result.get("challenge")
            pattern.review_verdict = "upheld"
            surviving.append(pattern)
        else:
            overturned += 1

    return surviving, overturned
