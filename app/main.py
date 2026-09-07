from pathlib import Path

import blackbox_engine
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.models import InvestigationResult
from app.pipeline import run_diagnosis
from app.service import investigate_target
from blackbox_engine.spec_loader import load_spec

app = FastAPI(
    title="BLACK BOX - Network Investigation System",
    description="Person 1 collection -> Person 2 analysis -> Person 3 diagnosis, end to end",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SPEC = load_spec(Path(blackbox_engine.__file__).parent / "hypotheses.yaml")

# In-memory baseline store, keyed by normalised target. A demo-scale
# stand-in for real persistence: the previous investigation's raw result
# becomes the baseline Person 2 compares the next one against.
_baselines: dict[str, InvestigationResult] = {}


class InvestigationRequest(BaseModel):
    target: str


@app.get("/")
def root():
    return {
        "service": "BLACK BOX Network Investigation System",
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
        result = investigate_target(target)

        return result.model_dump()

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Investigation failed: {str(e)}"
        )


@app.post("/diagnose")
async def diagnose(request: InvestigationRequest):
    """Run the full pipeline: collect -> compare against baseline -> diagnose.

    The previous run against this target (if any) becomes the baseline
    for path/performance comparison, then is replaced by this run's
    result for next time.
    """

    target = request.target.strip()

    if not target:
        raise HTTPException(
            status_code=400,
            detail="Target cannot be empty"
        )

    key = target.lower()

    try:
        current = investigate_target(target)
        baseline = _baselines.get(key)

        response = await run_diagnosis(_SPEC, baseline, current)

        _baselines[key] = current

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Diagnosis failed: {str(e)}"
        )