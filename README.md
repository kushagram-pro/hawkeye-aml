# HawkEye AML

HawkEye AML is a demo-grade anti-money-laundering investigation platform. It turns a set of transaction scenarios into an explainable case workflow with:

- a login-gated analyst dashboard
- a force-directed money trail graph
- a staged multi-agent investigation pipeline with live progress updates
- watchlist screening, pattern detection, adversarial review, risk scoring, case memory, and narrative output
- analyst chat, audit trail history, and PDF report export
- graceful fallback behavior when the LLM or backend is unavailable

The project is built as a split frontend/backend app:

- `src/` contains the React + Vite frontend
- `backend/` contains the FastAPI pipeline and scenario API

## What the demo does

The app is designed to help an analyst:

1. Sign in with demo credentials.
2. Pick a scenario or upload a custom transaction file.
3. Run the investigation pipeline.
4. Review suspicious accounts, flagged patterns, watchlist hits, and plain-language explanations.
5. Inspect prior-case matches, adversarial review notes, and an executive summary.
6. Ask follow-up questions in the case chat assistant and review the audit trail.
7. Download a PDF report for completed investigations.

The backend pipeline follows these visible stages:

- ingestion
- watchlist screening
- pattern detection
- adversarial review
- risk scoring
- case memory
- narrative generation

An executive summary is generated after the pipeline completes.

## Repository Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── pipeline/
│   │   └── data/
│   └── requirements.txt
├── src/
│   ├── components/
│   ├── services/
│   ├── data/
│   └── Dashboard.tsx
├── package.json
└── README.md
```

## Features

- Login with a shared demo account
- Scenario picker for seeded AML typologies
- CSV or JSON upload support for custom investigations
- Streaming pipeline progress over SSE
- Watchlist screening for repeat-offender or prior-case matches
- Interactive graph visualization of accounts and transfers
- Risk-ranked suspicious accounts and patterns
- Adversarial second-pass review to challenge false positives
- Case memory that links current findings to similar historical patterns
- Auto-generated investigator narrative, next steps, and executive summary
- In-case analyst chat grounded in the completed investigation result
- Persistent audit trail for investigation runs and analyst questions
- PDF report export for completed runs

## Tech Stack

- Frontend: React, TypeScript, Vite
- Visualization: `react-force-graph-2d`
- Backend: FastAPI, Pydantic
- Runtime orchestration: async Python pipeline with SSE streaming
- Reporting: ReportLab, NetworkX, Matplotlib

## Getting Started

### Prerequisites

- Node.js 18+ recommended
- Python 3.11+ recommended
- `pip`
- Optional: Ollama if you want local LLM support

### 1. Install frontend dependencies

```bash
npm install
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Start the backend

From the `backend/` directory:

```bash
uvicorn app.main:app --reload
```

The backend runs on `http://127.0.0.1:8000` by default.

### 4. Start the frontend

From the repository root:

```bash
npm run dev
```

The Vite app runs on `http://localhost:5173` by default.

## Demo Login

The backend uses a single shared login by default:

- Username: `admin`
- Password: `hawkeye2026`

These can be overridden with environment variables:

- `AUTH_USERNAME`
- `AUTH_PASSWORD`

## Backend Behavior

The backend supports a deterministic fallback flow so the demo can still run if the LLM is unavailable:

- rule-based detection still identifies suspicious patterns
- watchlist screening and case memory still operate from local data
- adversarial review falls back to keeping the original confirmed pattern
- fallback scoring assigns risk and confidence
- fallback narratives explain the finding in plain language
- cached investigation results can be used if a live run fails or times out
- LLM calls are time-bounded so the full pipeline can degrade gracefully instead of hanging

### LLM provider

By default, the backend is set up to use a local Ollama model.

If you want to use Anthropic instead, set:

```bash
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your_key_here
```

If the LLM cannot be reached, the pipeline falls back to deterministic output and still completes.

### Runtime guardrails

The investigation pipeline is designed to stay demo-friendly:

- individual LLM calls are bounded by short per-call timeouts
- the full pipeline has a hard runtime cap and falls back to cached or deterministic output if needed
- the backend still returns explainable results even when a live reasoning pass is unavailable

## API Overview

- `GET /health` - health check
- `GET /scenarios` - list available scenarios
- `GET /scenarios/{id}` - fetch a scenario's raw transactions
- `POST /scenarios/upload` - upload a CSV or JSON transaction set
- `DELETE /scenarios/{id}` - delete an uploaded scenario
- `POST /investigate/{id}` - stream pipeline events over SSE
- `GET /investigate/{id}/result` - fetch the last completed result
- `POST /investigate/{id}/ask` - ask grounded follow-up questions about a completed case
- `GET /investigate/{id}/audit` - fetch the investigation and chat audit trail
- `GET /investigate/{id}/report.pdf` - download a PDF report

## Scenario Data

Seeded scenarios live in:

```text
backend/app/data/scenarios/
```

Cached completed results live in:

```text
backend/app/data/cache/
```

## Input Format

Uploads must contain at least these transaction fields:

- `from_account`
- `to_account`
- `amount`
- `timestamp`

An optional `currency` field may also be included.

Accepted upload formats:

- `.csv`
- `.json`

## Development Notes

- The frontend is designed to keep working even if the backend is cold, by falling back to mock data.
- Investigation results are stored in memory on the backend and are lost on restart.
- Audit trail and pattern memory are persisted to local JSON files under `backend/app/data/`.
- The PDF report endpoint only works after a scenario has completed an investigation run.

## Useful Commands

```bash
npm run dev
npm run build
cd backend && uvicorn app.main:app --reload
```

## License

No license file was provided in the repository. Add one if you plan to distribute the project.
