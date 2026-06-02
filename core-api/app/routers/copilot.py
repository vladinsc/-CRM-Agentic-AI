from fastapi import APIRouter, Depends, HTTPException
from app.routers.leads import _ollama_lock
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from pydantic import BaseModel, ConfigDict
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
import base64
import os
import logging
import httpx
from app.database import get_db
from app.models import Lead, CopilotResult, AgentActivity, ConnectedAccount
from app.auth import get_current_user
from app.google_auth import get_gmail_service
from app.config import settings

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 24

router = APIRouter(prefix="/leads", tags=["copilot"])


class CopilotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    winning_argument: str
    draft_message: str
    confidence: float
    generated_at: datetime
    is_cached: bool


def _build_copilot_payload(lead: Lead) -> dict:
    from app.routers.leads import _format_deal_value
    return {
        "id": lead.id,
        "name": lead.name,
        "company": lead.company,
        "role": lead.role,
        "email": lead.email,
        "deal_value_display": _format_deal_value(lead.deal_value, lead.currency),
        "last_activity_description": lead.last_activity_description,
        "signals": lead.signals or [],
        "intent_score": lead.intent_score,
    }


def _call_copilot_agent(lead: Lead) -> dict:
    payload = _build_copilot_payload(lead)
    with httpx.Client(timeout=90.0) as client:
        try:
            response = client.post(f"{settings.ai_service_url}/agent/copilot", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"AI Service error {e.response.status_code}: {e.response.text}")
            raise e
        except Exception as e:
            logger.error(f"AI Service connection failed: {str(e)}")
            raise e


def _upsert_copilot_result(db: Session, lead: Lead, result: dict) -> CopilotResult:
    now = datetime.now(timezone.utc)
    snapshot = {
        "name": lead.name,
        "company": lead.company,
        "role": lead.role,
        "signals": lead.signals or [],
        "intent_score": lead.intent_score,
        "last_activity_description": lead.last_activity_description,
    }

    stmt = pg_insert(CopilotResult).values(
        lead_id=lead.id,
        winning_argument=result["winning_argument"],
        draft_message=result["draft_message"],
        confidence=result["confidence"],
        model_used=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        generated_at=now,
        lead_snapshot=snapshot,
    ).on_conflict_do_update(
        index_elements=["lead_id"],
        set_={
            "winning_argument": result["winning_argument"],
            "draft_message": result["draft_message"],
            "confidence": result["confidence"],
            "model_used": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            "generated_at": now,
            "lead_snapshot": snapshot,
        },
    )
    db.execute(stmt)
    db.commit()
    return db.query(CopilotResult).filter(CopilotResult.lead_id == lead.id).first()


def _log_activity(db: Session, lead: Lead) -> None:
    activity = AgentActivity(
        lead_id=lead.id,
        lead_name=lead.name,
        agent_name="CopilotAgent",
        action_type="insight",
        message=f"Generated co-pilot insights for {lead.name}",
        payload={},
        status="completed",
    )
    db.add(activity)
    db.commit()


@router.get("/{lead_id}/copilot", response_model=CopilotResponse)
def get_copilot(
    lead_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returnează copilot result pentru un lead.
    Cache-first: dacă există și generated_at < 24h, returnează din cache fără LLM call.
    Altfel, apelează CopilotAgent, persistă, returnează.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        (Lead.assigned_to == current_user.id) | (Lead.assigned_to == None),  # noqa: E711
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    cached = db.query(CopilotResult).filter(CopilotResult.lead_id == lead_id).first()
    if cached and cached.generated_at:
        age = datetime.now(timezone.utc) - cached.generated_at.replace(tzinfo=timezone.utc)
        if age < timedelta(hours=CACHE_TTL_HOURS):
            return CopilotResponse(
                winning_argument=cached.winning_argument or "",
                draft_message=cached.draft_message or "",
                confidence=cached.confidence or 0.5,
                generated_at=cached.generated_at,
                is_cached=True,
            )

    try:
        result = _call_copilot_agent(lead)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

    saved = _upsert_copilot_result(db, lead, result)
    _log_activity(db, lead)

    return CopilotResponse(
        winning_argument=saved.winning_argument or "",
        draft_message=saved.draft_message or "",
        confidence=saved.confidence or 0.5,
        generated_at=saved.generated_at,
        is_cached=False,
    )


@router.post("/{lead_id}/copilot/regenerate", response_model=CopilotResponse)
def regenerate_copilot(
    lead_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Forțează regenerarea copilot result, ignorând cache-ul existent."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        (Lead.assigned_to == current_user.id) | (Lead.assigned_to == None),  # noqa: E711
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    acquired = _ollama_lock.acquire(timeout=5)
    try:
        result = _call_copilot_agent(lead)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
    finally:
        if acquired:
            _ollama_lock.release()

    saved = _upsert_copilot_result(db, lead, result)
    _log_activity(db, lead)

    return CopilotResponse(
        winning_argument=saved.winning_argument or "",
        draft_message=saved.draft_message or "",
        confidence=saved.confidence or 0.5,
        generated_at=saved.generated_at,
        is_cached=False,
    )


@router.post("/{lead_id}/copilot/send-email")
def send_copilot_email(
    lead_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        (Lead.assigned_to == current_user.id) | (Lead.assigned_to == None),  # noqa: E711
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    cached = db.query(CopilotResult).filter(CopilotResult.lead_id == lead_id).first()
    if not cached or not cached.draft_message:
        raise HTTPException(
            status_code=400,
            detail="No draft message available. Generate copilot insights first.",
        )

    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == current_user.id,
        ConnectedAccount.provider == "google",
    ).first()
    if not account:
        raise HTTPException(
            status_code=400,
            detail="No connected Google account. Connect Gmail in Settings.",
        )

    service = get_gmail_service(account)
    if not service:
        raise HTTPException(
            status_code=400,
            detail="Gmail connection failed. Your Google account token has expired — please reconnect in Settings.",
        )

    try:
        message = MIMEText(cached.draft_message)
        message["to"] = lead.email
        message["subject"] = f"Following up — {lead.company}"
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except Exception as e:
        logger.error("Gmail send failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to send email: {str(e)}")

    activity = AgentActivity(
        lead_id=lead.id,
        lead_name=lead.name,
        agent_name="CopilotAgent",
        action_type="email_sent",
        message=f"Sent AI-drafted email to {lead.name} <{lead.email}>",
        payload={},
        status="completed",
    )
    db.add(activity)
    db.commit()

    return {"message": "Email sent successfully", "to": lead.email}
