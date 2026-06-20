import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path

from app.pipeline.agent1_ingestion import ingest
from app.pipeline.agent2_detection import detect_patterns
from app.pipeline.agent3_scoring import score_patterns
from app.pipeline.agent4_narrative import generate_narratives
from app.schemas import InvestigationGraph, PipelineEvent

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
CACHE_DIR = DATA_DIR / "cache"
PIPELINE_TIMEOUT_SECONDS = 55

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
    raw_transactions = load_scenario_transactions(scenario_id)

    yield PipelineEvent(stage="ingestion", status="started")
    graph = ingest(scenario_id, raw_transactions)
    yield PipelineEvent(stage="ingestion", status="completed", data={"account_count": len(graph.accounts)})

    yield PipelineEvent(stage="pattern_detection", status="started")
    flagged = await detect_patterns(graph)
    graph.flagged_patterns = flagged
    yield PipelineEvent(
        stage="pattern_detection", status="completed", data={"patterns_found": len(flagged)}
    )

    yield PipelineEvent(stage="risk_scoring", status="started")
    graph.flagged_patterns = await score_patterns(graph, graph.flagged_patterns)
    yield PipelineEvent(stage="risk_scoring", status="completed")

    yield PipelineEvent(stage="narrative", status="started")
    graph.flagged_patterns = await generate_narratives(graph, graph.flagged_patterns)
    yield PipelineEvent(stage="narrative", status="completed")

    last_results[scenario_id] = graph
    yield PipelineEvent(stage="pipeline", status="completed", data=graph.model_dump())


async def run_pipeline(scenario_id: str) -> AsyncGenerator[PipelineEvent, None]:
    queue: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()

    async def produce():
        try:
            async with asyncio.timeout(PIPELINE_TIMEOUT_SECONDS):
                async for event in _run_pipeline_stages(scenario_id):
                    await queue.put(event)
        except Exception:
            cached = load_cached_result(scenario_id)
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
