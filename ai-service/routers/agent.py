from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from agents import research_agent, copilot_agent, icp_match_agent

router = APIRouter(tags=["agent"])


class LeadPayload(BaseModel):
    id: int
    name: str
    company: str
    role: str
    email: str
    deal_value_display: Optional[str] = None
    last_activity_description: Optional[str] = None
    website_text: Optional[str] = None


class IcpMatchLead(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None
    website_text: Optional[str] = None


class IcpMatchPayload(BaseModel):
    lead: IcpMatchLead
    icp: dict   # the ICP raw_inputs (target_persona, target_company, ...)


class IcpMatchResult(BaseModel):
    match: bool
    score: int
    reasoning: str


class CopilotPayload(LeadPayload):
    signals: list[str] = []
    intent_score: Optional[int] = None


class ResearchResult(BaseModel):
    intent_score: int
    signals: list[str]
    summary: str
    confidence: float


class CopilotResult(BaseModel):
    winning_argument: str
    draft_message: str
    confidence: float


@router.post("/research", response_model=ResearchResult)
def research_lead(payload: LeadPayload):
    """Rulează LeadResearchAgent pentru un lead și returnează scorul de intenție."""
    try:
        result = research_agent.run(payload.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/copilot", response_model=CopilotResult)
def copilot_lead(payload: CopilotPayload):
    """Rulează CopilotAgent pentru un lead și returnează winning argument + draft email."""
    try:
        result = copilot_agent.run(payload.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@router.post("/icp-match", response_model=IcpMatchResult)
def icp_match(payload: IcpMatchPayload):
    """Decide whether a lead matches the user's Ideal Customer Profile."""
    try:
        result = icp_match_agent.run(payload.lead.model_dump(), payload.icp)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
