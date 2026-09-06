from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.service import investigate_target


app = FastAPI(
    title="BLACK BOX - Network Data Collector",
    description="Person 1: Network Data Collection API",
    version="1.0.0"
)


class InvestigationRequest(BaseModel):
    target: str


@app.get("/")
def root():
    return {
        "service": "BLACK BOX Network Data Collector",
        "status": "running",
        "role": "Person 1 - Network Data Collection"
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