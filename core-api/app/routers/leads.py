from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, computed_field
from typing import Optional
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import csv
import io
import os
import logging
import httpx
from app.database import get_db, SessionLocal
from app.models import Lead, AgentActivity, User
from app.auth import get_current_user

logger = logging.getLogger(__name__)

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")

router = APIRouter(prefix="/leads", tags=["leads"])

CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£", "RON": "RON "}


def _format_deal_value(deal_value: Optional[Decimal], currency: str) -> Optional[str]:
    """Formatează deal value cu simbolul corect al monedei."""
    if deal_value is None:
        return None
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    return f"{symbol}{int(deal_value):,}"


# ── Schemas ──────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    name: str
    company: str
    role: str
    email: str
    phone: Optional[str] = None
    deal_value: Optional[Decimal] = None
    currency: str = "EUR"
    last_activity_description: Optional[str] = None
    status: str = "new"


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    deal_value: Optional[Decimal] = None
    currency: Optional[str] = None
    last_activity_description: Optional[str] = None
    status: Optional[str] = None


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company: str
    role: str
    email: str
    phone: Optional[str]
    deal_value: Optional[Decimal]
    currency: str
    last_activity_description: Optional[str]
    intent_score: Optional[int]
    last_researched_at: Optional[datetime]
    signals: list
    assigned_to: Optional[int]
    status: str
    created_at: datetime

    @computed_field
    @property
    def score(self) -> Optional[int]:
        """Alias for intent_score — used by frontend."""
        return self.intent_score

    @computed_field
    @property
    def deal_value_display(self) -> Optional[str]:
        """Pre-formatted deal value for frontend (e.g. '€45,000')."""
        return _format_deal_value(self.deal_value, self.currency)


# ── Background research ───────────────────────────────────────────────────────

def _run_research_in_background(lead_id: int) -> None:
    """
    Apelează ai-service și persistă rezultatele pentru un lead.
    Rulează în background după crearea unui lead — nu blochează răspunsul.
    Folosește propria sesiune DB (nu cea din request, care e deja închisă).
    """
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return

        payload = {
            "id": lead.id,
            "name": lead.name,
            "company": lead.company,
            "role": lead.role,
            "email": lead.email,
            "deal_value_display": _format_deal_value(lead.deal_value, lead.currency),
            "last_activity_description": lead.last_activity_description,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(f"{AI_SERVICE_URL}/agent/research", json=payload)
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPError as e:
            logger.warning(f"Background research failed for lead {lead_id}: {e}")
            return

        lead.intent_score = result["intent_score"]
        lead.signals = result["signals"]
        lead.last_researched_at = datetime.now(timezone.utc)

        activity = AgentActivity(
            lead_id=lead.id,
            lead_name=lead.name,
            agent_name="LeadResearchAgent",
            action_type="research",
            message=result["summary"],
            payload=result,
            status="completed",
        )
        db.add(activity)
        db.commit()
        logger.info(f"Background research completed for lead {lead_id}, score={result['intent_score']}")

    except Exception as e:
        logger.error(f"Unexpected error in background research for lead {lead_id}: {e}")
        db.rollback()
    finally:
        db.close()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[LeadResponse])
def list_leads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all leads assigned to the current user, sorted by intent_score DESC."""
    leads = (
        db.query(Lead)
        .filter(Lead.assigned_to == current_user.id)
        .order_by(Lead.intent_score.desc().nulls_last())
        .all()
    )
    return leads


@router.post("", response_model=LeadResponse, status_code=201)
def create_lead(
    body: LeadCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new lead and trigger background research automatically."""
    lead = Lead(**body.model_dump(), assigned_to=current_user.id)
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Pornește research în background — răspunsul e returnat imediat
    background_tasks.add_task(_run_research_in_background, lead.id)

    return lead


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single lead by ID."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.assigned_to == current_user.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    body: LeadUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Partially update a lead."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.assigned_to == current_user.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=204)
def delete_lead(
    lead_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a lead."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.assigned_to == current_user.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    db.delete(lead)
    db.commit()


@router.post("/{lead_id}/research", response_model=LeadResponse)
def research_lead(
    lead_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Declanșează LeadResearchAgent pentru un lead.
    Apelează ai-service, persistă rezultatele și returnează lead-ul îmbogățit.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.assigned_to == current_user.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # ── Apelează ai-service ───────────────────────────────────────────────────
    payload = {
        "id": lead.id,
        "name": lead.name,
        "company": lead.company,
        "role": lead.role,
        "email": lead.email,
        "deal_value_display": _format_deal_value(lead.deal_value, lead.currency),
        "last_activity_description": lead.last_activity_description,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{AI_SERVICE_URL}/agent/research", json=payload)
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")

    # ── Persistă rezultatele în leads ────────────────────────────────────────
    lead.intent_score = result["intent_score"]
    lead.signals = result["signals"]
    lead.last_researched_at = datetime.now(timezone.utc)

    # ── Inserează în agent_activities ────────────────────────────────────────
    activity = AgentActivity(
        lead_id=lead.id,
        lead_name=lead.name,
        agent_name="LeadResearchAgent",
        action_type="research",
        message=result["summary"],
        payload=result,
        status="completed",
    )
    db.add(activity)
    db.commit()
    db.refresh(lead)

    return lead


# ── CSV Import ────────────────────────────────────────────────────────────────

# Mapare flexibilă: numele coloanei din CSV → câmpul intern
_COL_MAP = {
    "name": "name", "full name": "name", "contact name": "name",
    "first name": "_first", "last name": "_last",
    "company": "company", "company name": "company", "organization": "company",
    "role": "role", "job title": "role", "position": "role", "title": "role",
    "email": "email", "email address": "email",
    "phone": "phone", "phone number": "phone", "mobile": "phone",
    "deal value": "deal_value", "amount": "deal_value", "deal amount": "deal_value", "value": "deal_value",
    "currency": "currency",
    "last activity": "last_activity_description", "notes": "last_activity_description",
    "description": "last_activity_description", "activity": "last_activity_description",
    "status": "status",
}


def _map_row(row: dict) -> dict:
    """Mapează un rând CSV la câmpurile modelului Lead."""
    mapped: dict = {}
    for col, val in row.items():
        key = _COL_MAP.get(col.lower().strip())
        if key and val.strip():
            mapped[key] = val.strip()

    # Combină first name + last name dacă nu există "name"
    if "name" not in mapped:
        first = mapped.pop("_first", "")
        last = mapped.pop("_last", "")
        full = f"{first} {last}".strip()
        if full:
            mapped["name"] = full

    return mapped


@router.post("/import")
async def import_leads_csv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Importă lead-uri dintr-un fișier CSV.
    Suportă exporturi din LinkedIn, HubSpot, Excel sau format generic.
    Returnează câte rânduri au fost importate și câte au fost sărite.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # utf-8-sig elimină BOM-ul Excel
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    imported, skipped, errors = 0, 0, []

    for i, row in enumerate(reader, start=2):  # start=2 pt că linia 1 e header
        mapped = _map_row(row)

        # Câmpuri obligatorii
        if not mapped.get("name") or not mapped.get("email"):
            skipped += 1
            errors.append(f"Row {i}: missing name or email — skipped")
            continue

        # Parsează deal_value
        deal_value = None
        if mapped.get("deal_value"):
            try:
                clean = mapped["deal_value"].replace(",", "").replace("€", "").replace("$", "").replace("£", "").strip()
                deal_value = Decimal(clean)
            except InvalidOperation:
                pass  # ignoră valori invalide

        lead = Lead(
            name=mapped["name"],
            company=mapped.get("company", "—"),
            role=mapped.get("role", "—"),
            email=mapped["email"],
            phone=mapped.get("phone"),
            deal_value=deal_value,
            currency=mapped.get("currency", "EUR").upper()[:10],
            last_activity_description=mapped.get("last_activity_description"),
            status=mapped.get("status", "new"),
            assigned_to=current_user.id,
        )
        db.add(lead)
        db.flush()  # obținem lead.id fără commit

        background_tasks.add_task(_run_research_in_background, lead.id)
        imported += 1

    db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10],  # max 10 erori în răspuns
    }
