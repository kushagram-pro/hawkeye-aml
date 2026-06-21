import asyncio
import json
import os
import time
from collections import Counter
from collections.abc import AsyncGenerator
from pathlib import Path

from app.pipeline import audit_log, pattern_memory, watchlist
from app.pipeline.agent1_ingestion import ingest
from app.pipeline.agent2_detection import detect_patterns
from app.pipeline.agent2b_adversarial import run_adversarial_review
from app.pipeline.agent3_scoring import score_patterns
from app.pipeline.agent4_narrative import generate_narratives
from app.pipeline.agent5_summary import generate_executive_summary
from app.schemas import InvestigationGraph, PipelineEvent

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
CACHE_DIR = DATA_DIR / "cache"
PIPELINE_TIMEOUT_SECONDS = float(os.getenv("PIPELINE_TIMEOUT_SECONDS", "115"))

last_results: dict[str, InvestigationGraph] = {}


def load_scenario_transactions(scenario_id: str) -> list[dict]:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)["transactions"]


def load_cached_result(scenario_id: str) -> InvestigationGraph:
    path = CACHE_DIR / f"{scenario_id}_result.json"
    with open(path, encoding="utf-8") as f:
        return InvestigationGraph(**json.load(f))


async def _run_pipeline_stages(scenario_id: str) -> AsyncGenerator[PipelineEvent, None]:
    started_at = time.monotonic()
    raw_transactions = load_scenario_transactions(scenario_id)

    yield PipelineEvent(stage="ingestion", status="started")
    graph = ingest(scenario_id, raw_transactions)
    yield PipelineEvent(
        stage="ingestion",
        status="completed",
        data={
            "account_count": len(graph.accounts),
            "transaction_count": len(graph.transactions),
        },
    )

    yield PipelineEvent(stage="watchlist_screening", status="started")
    watchlist_hits = watchlist.screen(scenario_id, graph)
    for account in graph.accounts:
        note = watchlist_hits.get(account.id)
        if note:
            account.watchlist_note = note
            if "watchlist" not in account.flags:
                account.flags.append("watchlist")
    yield PipelineEvent(
        stage="watchlist_screening",
        status="completed",
        data={"accounts_flagged": len(watchlist_hits)},
    )

    yield PipelineEvent(stage="pattern_detection", status="started")
    flagged = await detect_patterns(graph)
    graph.flagged_patterns = flagged
    yield PipelineEvent(
        stage="pattern_detection",
        status="completed",
        data={
            "patterns_found": len(flagged),
            "pattern_types": dict(Counter(p.pattern_type for p in flagged)),
        },
    )

    yield PipelineEvent(stage="adversarial_review", status="started")
    candidates_before_review = len(graph.flagged_patterns)
    graph.flagged_patterns, overturned_count = await run_adversarial_review(graph, graph.flagged_patterns)
    yield PipelineEvent(
        stage="adversarial_review",
        status="completed",
        data={
            "patterns_reviewed": candidates_before_review,
            "patterns_upheld": len(graph.flagged_patterns),
            "patterns_overturned": overturned_count,
        },
    )

    yield PipelineEvent(stage="risk_scoring", status="started")
    graph.flagged_patterns = await score_patterns(graph, graph.flagged_patterns)
    scores = [p.risk_score for p in graph.flagged_patterns]
    yield PipelineEvent(
        stage="risk_scoring",
        status="completed",
        data={
            "average_risk_score": round(sum(scores) / len(scores), 1) if scores else None,
            "highest_risk_score": max(scores) if scores else None,
            "high_confidence_count": sum(1 for p in graph.flagged_patterns if p.confidence == "high"),
        },
    )

    yield PipelineEvent(stage="case_memory", status="started")
    cases_with_matches = 0
    for pattern in graph.flagged_patterns:
        pattern.similar_past_cases = pattern_memory.find_similar(scenario_id, pattern)
        if pattern.similar_past_cases:
            cases_with_matches += 1
        pattern_memory.record(scenario_id, pattern)
    yield PipelineEvent(
        stage="case_memory",
        status="completed",
        data={"patterns_with_precedent": cases_with_matches},
    )

    yield PipelineEvent(stage="narrative", status="started")
    graph.flagged_patterns = await generate_narratives(graph, graph.flagged_patterns)
    graph.executive_summary = await generate_executive_summary(graph, graph.flagged_patterns)
    yield PipelineEvent(
        stage="narrative",
        status="completed",
        data={
            "narratives_generated": sum(1 for p in graph.flagged_patterns if p.narrative),
            "executive_summary": graph.executive_summary,
        },
    )

    last_results[scenario_id] = graph
    audit_log.record_run(scenario_id, graph, overturned_count, time.monotonic() - started_at)
    yield PipelineEvent(stage="pipeline", status="completed", data=graph.model_dump())


async def run_pipeline(scenario_id: str) -> AsyncGenerator[PipelineEvent, None]:
    queue: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()

    async def produce():
        try:
            async with asyncio.timeout(PIPELINE_TIMEOUT_SECONDS):
                async for event in _run_pipeline_stages(scenario_id):
                    await queue.put(event)
        except Exception:
            try:
                cached = load_cached_result(scenario_id)
            except (FileNotFoundError, OSError, ValueError):
                await queue.put(PipelineEvent(stage="pipeline", status="failed"))
                return
            last_results[scenario_id] = cached
            await queue.put(
                PipelineEvent(stage="pipeline", status="completed", data=cached.model_dump())
            )
        finally:
            await queue.put(None)

    producer_task = asyncio.create_task(produce())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event
    finally:
        await producer_task
