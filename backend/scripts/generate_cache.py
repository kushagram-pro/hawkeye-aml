"""Pre-generates the cached fallback result for each scenario by running the
real pipeline once and saving its output. Used as the demo-safety fallback
when a live pipeline run fails or times out (see orchestrator.py).

Run: python scripts/generate_cache.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.agent1_ingestion import ingest
from app.pipeline.agent2_detection import detect_patterns
from app.pipeline.agent3_scoring import score_patterns
from app.pipeline.agent4_narrative import generate_narratives
from app.pipeline.orchestrator import CACHE_DIR, load_scenario_transactions

SCENARIO_IDS = ["structuring", "layering", "mule_network"]


async def build_result(scenario_id: str):
    raw_transactions = load_scenario_transactions(scenario_id)
    graph = ingest(scenario_id, raw_transactions)
    graph.flagged_patterns = await detect_patterns(graph)
    graph.flagged_patterns = await score_patterns(graph, graph.flagged_patterns)
    graph.flagged_patterns = await generate_narratives(graph, graph.flagged_patterns)
    return graph


async def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for scenario_id in SCENARIO_IDS:
        graph = await build_result(scenario_id)
        path = CACHE_DIR / f"{scenario_id}_result.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(graph.model_dump(), f, indent=2)
        print(f"wrote {path} ({len(graph.flagged_patterns)} flagged patterns)")
        for p in graph.flagged_patterns:
            print(f"  - {p.pattern_type}: risk={p.risk_score} confidence={p.confidence}")
            print(f"    narrative: {p.narrative}")


if __name__ == "__main__":
    asyncio.run(main())
