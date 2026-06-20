import csv
import io
import json
import re
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.pipeline.orchestrator import SCENARIOS_DIR
from app.schemas import Transaction

router = APIRouter()

REQUIRED_COLUMNS = {"from_account", "to_account", "amount", "timestamp"}


def _parse_json(content: bytes) -> list[dict]:
    data = json.loads(content)
    if isinstance(data, dict):
        data = data.get("transactions", [])
    if not isinstance(data, list):
        raise HTTPException(400, "JSON file must contain a list of transactions or a {\"transactions\": [...]} object")
    return data


def _parse_csv(content: bytes) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    return list(reader)


@router.post("/scenarios/upload")
async def upload_transactions(file: UploadFile = File(...), name: str | None = Form(None)):
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".json"):
        raw = _parse_json(content)
    elif filename.endswith(".csv"):
        raw = _parse_csv(content)
    else:
        raise HTTPException(400, "Only .csv or .json files are supported")

    if not raw:
        raise HTTPException(400, "File contains no transactions")

    if not REQUIRED_COLUMNS.issubset(raw[0].keys()):
        raise HTTPException(400, f"File must contain columns: {', '.join(sorted(REQUIRED_COLUMNS))}")

    transactions = []
    for row in raw:
        try:
            transactions.append(
                Transaction(
                    from_account=str(row["from_account"]),
                    to_account=str(row["to_account"]),
                    amount=float(row["amount"]),
                    timestamp=str(row["timestamp"]),
                    currency=str(row.get("currency") or "INR"),
                ).model_dump()
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(400, f"Invalid transaction row: {exc}") from exc

    fallback_name = re.sub(r"\.(csv|json)$", "", file.filename or "Uploaded transactions", flags=re.IGNORECASE)
    display_name = (name or fallback_name).strip()[:80] or fallback_name

    scenario_id = f"upload-{uuid.uuid4().hex[:8]}"
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "scenario_id": scenario_id,
                "display_name": display_name,
                "seeded_pattern": None,
                "transactions": transactions,
            },
            f,
        )

    return {"scenario_id": scenario_id, "transaction_count": len(transactions), "name": display_name}
