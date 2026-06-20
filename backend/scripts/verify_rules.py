"""Sanity-checks the rule pre-filters against the generated scenarios (no LLM calls).
Run: python scripts/verify_rules.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.agent1_ingestion import ingest
from app.pipeline.agent2_detection import (
    _find_layering_candidates,
    _find_mule_network_candidates,
    _find_structuring_candidates,
)

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "scenarios"


def check(scenario_id: str):
    with open(SCENARIOS_DIR / f"{scenario_id}.json", encoding="utf-8") as f:
        raw = json.load(f)["transactions"]
    graph = ingest(scenario_id, raw)
    accounts_index = {a.id: a for a in graph.accounts}

    structuring = _find_structuring_candidates(graph.transactions)
    layering = _find_layering_candidates(graph.transactions)
    mule = _find_mule_network_candidates(graph.transactions, accounts_index)

    print(f"\n=== {scenario_id} ({len(graph.transactions)} tx, {len(graph.accounts)} accounts) ===")
    print(f"structuring candidates: {[(c[0].to_account, len(c)) for c in structuring]}")
    print(f"layering candidates: {[[t.from_account for t in c] + [c[-1].to_account] for c in layering]}")
    print(f"mule candidates: {[(c['source'], c['mules']) for c in mule]}")


if __name__ == "__main__":
    for scenario_id in ["structuring", "layering", "mule_network"]:
        check(scenario_id)
