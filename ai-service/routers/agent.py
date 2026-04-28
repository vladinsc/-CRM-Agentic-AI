from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from agents import research_agent

router = APIRouter(prefix="/agent", tags=["agent"])


class LeadPayload(BaseModel):
    id: int
    name: str
    company: str
    role: str
    email: str
    deal_value_display: Optional[str] = None
    last_activity_description: Optional[str] = None


class ResearchResult(BaseModel):
    intent_score: int
    signals: list[str]
    summary: str
    confidence: float


@router.post("/research", response_model=ResearchResult)
def research_lead(payload: LeadPayload):
    """Rulează LeadResearchAgent pentru un lead și returnează scorul de intenție."""
    try:
        result = research_agent.run(payload.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
