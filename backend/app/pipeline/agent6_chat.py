"""Chat with the case.

Lets an analyst ask free-text follow-up questions about a completed
investigation. Reuses the same InvestigationGraph the dashboard already
holds in memory - no extra retrieval step - and answers strictly from that
case's accounts, confirmed patterns, narratives, adversarial review notes,
and next steps, rather than inventing facts the pipeline never produced.
"""

from app.llm_client import call_llm
from app.schemas import ChatMessage, InvestigationGraph

SYSTEM_PROMPT = (
    "You are an AML investigation assistant helping an analyst review one "
    "specific completed investigation. You will be given the case data below "
    "(accounts, confirmed suspicious patterns, narratives, adversarial review "
    "notes, recommended next steps) and a question. Answer using ONLY that "
    "data - cite specific account IDs, amounts, or risk scores where relevant. "
    "All monetary amounts in this data are in Indian Rupees - always write them as "
    "'Rs. <amount>', never '$' or 'USD'. "
    "If the question cannot be answered from the case data given, say so "
    "plainly rather than guessing or inventing figures. Keep answers to 2-5 "
    "sentences. Respond with strict JSON only, with exactly one key named "
    "\"answer\" - no other key names, no nested objects: {\"answer\": \"...\"}"
)

FALLBACK_ANSWER = (
    "I can't reach the reasoning engine right now, so I can't answer that. "
    "The case data is still visible in the graph and insight panel above."
)

MAX_HISTORY_TURNS = 6


def _build_case_context(graph: InvestigationGraph) -> dict:
    flagged_account_ids = {account for pattern in graph.flagged_patterns for account in pattern.accounts_involved}

    return {
        "scenario_id": graph.scenario_id,
        "account_count": len(graph.accounts),
        "transaction_count": len(graph.transactions),
        "executive_summary": graph.executive_summary,
        "flagged_patterns": [
            {
                "pattern_type": pattern.pattern_type,
                "accounts_involved": pattern.accounts_involved,
                "risk_score": pattern.risk_score,
                "confidence": pattern.confidence,
                "contributing_factors": pattern.contributing_factors,
                "narrative": pattern.narrative,
                "adversarial_review": pattern.skeptic_challenge,
                "review_verdict": pattern.review_verdict,
                "next_steps": pattern.next_steps,
                "similar_past_cases": pattern.similar_past_cases,
            }
            for pattern in graph.flagged_patterns
        ],
        "flagged_accounts": [
            {
                "id": account.id,
                "total_in": account.total_in,
                "total_out": account.total_out,
                "transaction_count": account.transaction_count,
                "unique_counterparties": account.unique_counterparties,
                "risk_score": account.risk_score,
                "confidence": account.confidence,
                "flags": account.flags,
            }
            for account in graph.accounts
            if account.id in flagged_account_ids
        ],
    }


def _format_history(history: list[ChatMessage]) -> str:
    if not history:
        return "(none yet)"
    recent = history[-MAX_HISTORY_TURNS:]
    return "\n".join(f"{message.role}: {message.content}" for message in recent)


async def answer_question(graph: InvestigationGraph, question: str, history: list[ChatMessage]) -> str:
    user_prompt = (
        f"case_data: {_build_case_context(graph)}\n\n"
        f"conversation_so_far:\n{_format_history(history)}\n\n"
        f"question: {question}"
    )
    try:
        result = await call_llm(SYSTEM_PROMPT, user_prompt)
        return result.get("answer") or _best_effort_answer(result) or FALLBACK_ANSWER
    except Exception:
        return FALLBACK_ANSWER


def _best_effort_answer(result: dict) -> str | None:
    """The model occasionally ignores the requested {"answer": ...} shape and
    returns its own key names instead. Rather than discard a real response,
    stitch together whatever string values it did return."""
    strings = [value.strip() for value in result.values() if isinstance(value, str) and value.strip()]
    return " ".join(strings) if strings else None
