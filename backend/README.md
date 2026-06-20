# HawkEye AML — Backend

4-stage agent pipeline (ingestion → pattern detection → risk scoring → narrative) for the
NEXORA'26 AML investigation demo. See `app/schemas.py` for the shared JSON contract the
frontend builds against.

## Setup

```bash
cd backend
pip install -r requirements.txt
```

By default the pipeline calls a local Ollama model (no API key, no cost — good for a live demo):

```bash
ollama pull qwen2.5:7b-instruct
ollama serve
```

To use the Anthropic API instead, set:

```bash
export LLM_PROVIDER=claude
export ANTHROPIC_API_KEY=sk-...
```

If the LLM (either provider) is unreachable, every pipeline stage degrades gracefully to a
deterministic fallback (rule engine confirms its own flags, factor-weighted scoring, templated
narrative) — the pipeline still completes and still demos correctly, just with less nuanced text.

## Run

```bash
uvicorn app.main:app --reload
```

## Scenario data

Datasets live in `app/data/scenarios/*.json`; the pre-baked fallback results used when a live
run fails/times out live in `app/data/cache/*.json`. Regenerate either with:

```bash
python scripts/generate_scenarios.py
python scripts/verify_rules.py   # sanity-check the rule pre-filters with no LLM calls
python scripts/generate_cache.py # re-bakes the cache from a real (or fallback) pipeline run
```

## API

- `GET /scenarios` — list available scenarios
- `GET /scenarios/{id}` — raw transactions for a scenario
- `POST /investigate/{id}` — runs the pipeline, streams `PipelineEvent`s over SSE, final event carries the full `InvestigationGraph`
- `GET /investigate/{id}/result` — last completed result for a scenario, no re-run
