from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, investigate, report, scenarios, upload
from app.routes.auth import require_auth

app = FastAPI(title="HawkEye AML")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(scenarios.router, dependencies=[Depends(require_auth)])
app.include_router(investigate.router, dependencies=[Depends(require_auth)])
app.include_router(upload.router, dependencies=[Depends(require_auth)])
app.include_router(report.router, dependencies=[Depends(require_auth)])


@app.get("/health")
def health():
    return {"status": "ok"}
