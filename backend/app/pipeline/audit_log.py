"""Audit trail.

A persistent, file-backed log of everything the platform did on a case: every
completed pipeline run (which stages ran, what was confirmed, what the
adversarial reviewer overturned) and every chat question an analyst asked
about it. This is the "what happened and when, with a timestamp" record a
compliance review would actually ask for - separate from `pattern_memory`,
which is about recognizing repeat patterns rather than proving a trail.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import FlaggedPattern, InvestigationGraph

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "audit_log.json"

MAX_ENTRIES = 500


def _load() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    with open(LOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(entries: list[dict]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries[-MAX_ENTRIES:], f, indent=2)


def _append(entry: dict) -> None:
    entries = _load()
    entries.append(entry)
    _save(entries)


def record_run(
    scenario_id: str,
    graph: InvestigationGraph,
    overturned_count: int,
    elapsed_seconds: float,
) -> None:
    patterns: list[FlaggedPattern] = graph.flagged_patterns
    pattern_types = sorted({p.pattern_type for p in patterns})

    summary = (
        f"Investigation run on '{scenario_id}': {len(patterns)} pattern(s) confirmed "
        f"({', '.join(pattern_types) or 'none'}), {overturned_count} overturned by adversarial review."
    )

    _append(
        {
            "id": str(uuid.uuid4()),
            "type": "investigation_run",
            "scenario_id": scenario_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "details": {
                "account_count": len(graph.accounts),
                "transaction_count": len(graph.transactions),
                "patterns_confirmed": len(patterns),
                "patterns_overturned": overturned_count,
                "pattern_types": pattern_types,
                "highest_risk_score": max((p.risk_score for p in patterns), default=None),
                "elapsed_seconds": round(elapsed_seconds, 1),
                "executive_summary": graph.executive_summary,
            },
        }
    )


def record_chat(scenario_id: str, question: str, answer: str) -> None:
    _append(
        {
            "id": str(uuid.uuid4()),
            "type": "chat_message",
            "scenario_id": scenario_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": f"Analyst asked: \"{question}\"",
            "details": {"question": question, "answer": answer},
        }
    )


def get_log(scenario_id: str) -> list[dict]:
    entries = [entry for entry in _load() if entry["scenario_id"] == scenario_id]
    entries.sort(key=lambda entry: entry["timestamp"], reverse=True)
    return entries
