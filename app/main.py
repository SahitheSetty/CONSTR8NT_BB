from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.integration import run_investigation


app = FastAPI(
    title="BLACK BOX - Network Investigation API",
    description="Complete BLACK BOX investigation pipeline",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvestigationRequest(BaseModel):
    target: str


# Stores the previous raw investigation for each target.
# This allows Person 2 to compare the current investigation
# with the previous one during a retest.
previous_investigations: dict[str, dict] = {}


@app.get("/")
def root():
    return {
        "service": "BLACK BOX Network Investigation API",
        "status": "running",
        "pipeline": "Person 1 -> Person 2 -> Adapter -> Bayesian Engine"
    }


@app.post("/investigate")
def investigate(request: InvestigationRequest):
    target = request.target.strip()

    if not target:
        raise HTTPException(
            status_code=400,
            detail="Target cannot be empty"
        )

    try:
        previous_data = previous_investigations.get(target.lower())

        result = run_investigation(
            target=target,
            previous_data=previous_data
        )

        # Store the current raw data as the baseline for the
        # next investigation of the same target.
        previous_investigations[target.lower()] = {
            "target": result["target"],
            "timestamp": result["timestamp"],
            "investigationId": result["investigationId"],
            "dns": result["dns"],
            "http": result["http"],
            "path": result["rawPath"],
            "status": result["status"],
            "errors": result["errors"],
        }

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Investigation failed: {str(e)}"
        )