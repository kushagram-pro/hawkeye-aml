import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.pipeline import audit_log
from app.pipeline.agent6_chat import answer_question
from app.pipeline.orchestrator import last_results, run_pipeline
from app.schemas import AuditEntry, ChatRequest, ChatResponse, InvestigationGraph

router = APIRouter()


def _sse_format(event_dict: dict) -> str:
    return f"data: {json.dumps(event_dict)}\n\n"


@router.post("/investigate/{scenario_id}")
async def investigate(scenario_id: str):
    async def event_stream():
        async for event in run_pipeline(scenario_id):
            yield _sse_format(event.model_dump())

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/investigate/{scenario_id}/result", response_model=InvestigationGraph)
def get_result(scenario_id: str):
    if scenario_id not in last_results:
        raise HTTPException(status_code=404, detail="No completed investigation for this scenario yet")
    return last_results[scenario_id]


@router.post("/investigate/{scenario_id}/ask", response_model=ChatResponse)
async def ask(scenario_id: str, payload: ChatRequest):
    if scenario_id not in last_results:
        raise HTTPException(status_code=404, detail="No completed investigation for this scenario yet")
    graph = last_results[scenario_id]
    answer = await answer_question(graph, payload.question, payload.history)
    audit_log.record_chat(scenario_id, payload.question, answer)
    return ChatResponse(answer=answer)


@router.get("/investigate/{scenario_id}/audit", response_model=list[AuditEntry])
def get_audit_log(scenario_id: str):
    return audit_log.get_log(scenario_id)
