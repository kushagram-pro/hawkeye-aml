"""Cross-scenario pattern memory.

A lightweight, file-backed log of every confirmed pattern across all past
investigations (any scenario, any run). It needs no LLM and no vector store -
just a JSON list and a same-pattern-type lookup - but it lets a brand-new
investigation say "this resembles 2 prior cases" instead of treating every
run as if it were the platform's first.
"""

import json
from pathlib import Path

from app.schemas import FlaggedPattern

MEMORY_PATH = Path(__file__).resolve().parent.parent / "data" / "pattern_memory.json"


def _load() -> list[dict]:
    if not MEMORY_PATH.exists():
        return []
    with open(MEMORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(records: list[dict]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def all_records() -> list[dict]:
    return _load()


def find_similar(scenario_id: str, pattern: FlaggedPattern, limit: int = 2) -> list[str]:
    candidates = [
        record
        for record in _load()
        if record["pattern_type"] == pattern.pattern_type and record["scenario_id"] != scenario_id
    ]
    candidates.sort(key=lambda record: abs(record["risk_score"] - pattern.risk_score))

    return [
        f"Resembles a prior {record['pattern_type'].replace('_', ' ')} case from scenario "
        f"'{record['scenario_id']}' (risk {record['risk_score']}, {record['confidence']} confidence)."
        for record in candidates[:limit]
    ]


def record(scenario_id: str, pattern: FlaggedPattern) -> None:
    records = _load()
    key = (scenario_id, pattern.pattern_type, tuple(sorted(pattern.accounts_involved)))
    records = [
        record
        for record in records
        if (record["scenario_id"], record["pattern_type"], tuple(sorted(record["accounts_involved"]))) != key
    ]
    records.append(
        {
            "scenario_id": scenario_id,
            "pattern_type": pattern.pattern_type,
            "accounts_involved": pattern.accounts_involved,
            "risk_score": pattern.risk_score,
            "confidence": pattern.confidence,
            "reasoning": pattern.reasoning,
        }
    )
    _save(records)
