import json

from fastapi import APIRouter, HTTPException

from app.pipeline.orchestrator import SCENARIOS_DIR, last_results
from app.schemas import ScenarioMeta

router = APIRouter()

SCENARIO_METADATA = {
    "structuring": "Many sub-threshold transfers converging on one account within a tight time window.",
    "layering": "Money passed through a chain of intermediary accounts before reaching its final destination.",
    "mule_network": "One source account fans out to many accounts that each independently cash out.",
}


@router.get("/scenarios", response_model=list[ScenarioMeta])
def list_scenarios():
    scenarios = []
    for scenario_id, description in SCENARIO_METADATA.items():
        path = SCENARIOS_DIR / f"{scenario_id}.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        scenarios.append(
            ScenarioMeta(
                id=scenario_id,
                name=scenario_id.replace("_", " ").title(),
                description=description,
                transaction_count=len(data["transactions"]),
            )
        )

    if SCENARIOS_DIR.exists():
        for path in sorted(SCENARIOS_DIR.glob("upload-*.json")):
            scenario_id = path.stem
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            scenarios.append(
                ScenarioMeta(
                    id=scenario_id,
                    name=data.get("display_name") or f"Uploaded — {scenario_id.removeprefix('upload-')}",
                    description="Custom transaction set uploaded for this investigation.",
                    transaction_count=len(data["transactions"]),
                    deletable=True,
                )
            )

    return scenarios


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str):
    if not scenario_id.startswith("upload-"):
        raise HTTPException(status_code=400, detail="Only uploaded scenarios can be deleted")

    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")

    path.unlink()
    last_results.pop(scenario_id, None)
    return {"deleted": scenario_id}
