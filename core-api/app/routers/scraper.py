import os
import logging
import threading
from uuid import uuid4
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lead, ScrapeJob, ICPBlueprint
from app.auth import get_current_user, get_current_user_flexible
from app.models import User

logger = logging.getLogger(__name__)

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")

router = APIRouter(prefix="/scraper", tags=["scraper"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ExtJobCreate(BaseModel):
    """Job created by the browser extension — no server-side scraping involved."""
    query: str


class ExtJobPatch(BaseModel):
    status: Optional[str] = None
    scraped_count: Optional[int] = None


class ScrapeJobResponse(BaseModel):
    id: int
    query: str
    pages_requested: int
    status: str
    scraped_count: int
    leads_created: int
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScrapedLeadItem(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    profile_url: Optional[str] = None
    company_url: Optional[str] = None


class InternalLeadsPayload(BaseModel):
    leads: list[ScrapedLeadItem]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_research_thread(lead_id: int) -> None:
    """Trigger research for a scraped lead in a background thread."""
    from app.routers.leads import _run_research_in_background
    _run_research_in_background(lead_id)


def _get_active_icp_inputs(db: Session, user_id: int) -> Optional[dict]:
    """Return the user's active ICP raw_inputs dict, or None if they have none."""
    icp = db.query(ICPBlueprint).filter(
        ICPBlueprint.user_id == user_id,
        ICPBlueprint.is_active.is_(True),
    ).first()
    return icp.raw_inputs if icp else None


def _icp_match(item: "ScrapedLeadItem", icp_inputs: dict) -> dict:
    """Ask the ai-service whether a scraped lead fits the ICP. Fail-closed on error."""
    payload = {
        "lead": {
            "name": item.name,
            "company": item.company,
            "role": item.title,
            "location": item.location,
        },
        "icp": icp_inputs,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{AI_SERVICE_URL}/agent/icp-match", json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.warning(f"ICP-match call failed for '{item.name}': {e}")
        # Fail-closed: if the agent is unreachable, mark as non-match (reviewable)
        # rather than silently flooding the pipeline.
        return {"match": False, "score": 0, "reasoning": "ICP match unavailable."}


def _ingest_leads(db: Session, job: ScrapeJob, leads: list["ScrapedLeadItem"]) -> dict:
    """
    Dedup + create Lead rows for a batch of scraped leads, gated on the user's
    active ICP: matching leads become status='new' and get researched; non-matching
    leads are saved with status='rejected_icp' and skip research. Shared by the
    internal and extension endpoints.
    """
    user_id = job.user_id
    icp_inputs = _get_active_icp_inputs(db, user_id)

    matched = 0
    rejected = 0
    skipped = 0

    for item in leads:
        if not item.name:
            skipped += 1
            continue

        # Primary dedup: linkedin_url
        if item.profile_url:
            exists = db.query(Lead).filter(
                Lead.linkedin_url == item.profile_url,
                Lead.assigned_to == user_id,
            ).first()
            if exists:
                skipped += 1
                continue

        # Fallback dedup: name + company
        if item.name and item.company:
            exists = db.query(Lead).filter(
                Lead.name == item.name,
                Lead.company == item.company,
                Lead.assigned_to == user_id,
            ).first()
            if exists:
                skipped += 1
                continue

        # ICP gate
        match = _icp_match(item, icp_inputs) if icp_inputs else {"match": True, "reasoning": ""}
        is_match = bool(match.get("match"))

        placeholder_email = f"scraped_li_{uuid4().hex[:8]}@placeholder.invalid"
        note = "Scraped from LinkedIn Sales Navigator"
        if item.location:
            note += f" · {item.location}"
        if not is_match and match.get("reasoning"):
            note += f" · ICP mismatch: {match['reasoning']}"

        lead = Lead(
            name=item.name,
            company=item.company or "—",
            role=item.title or "—",
            email=placeholder_email,
            last_activity_description=note,
            linkedin_url=item.profile_url,
            company_url=item.company_url,
            status="new" if is_match else "rejected_icp",
            assigned_to=user_id,
        )
        db.add(lead)
        db.flush()

        if is_match:
            # Only research leads that passed the ICP gate.
            threading.Thread(
                target=_run_research_thread,
                args=(lead.id,),
                daemon=True,
            ).start()
            matched += 1
        else:
            rejected += 1

    job.leads_created = (job.leads_created or 0) + matched
    job.scraped_count = (job.scraped_count or 0) + matched + rejected + skipped
    db.commit()

    return {"matched": matched, "rejected": rejected, "skipped": skipped,
            "accepted": matched}  # 'accepted' kept for backward-compat


# ── Scrape job endpoints (read-only; jobs are created via /ext/jobs) ──────────

@router.get("/jobs", response_model=list[ScrapeJobResponse])
def list_scrape_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List scrape jobs for the current user (most recent first)."""
    jobs = (
        db.query(ScrapeJob)
        .filter(ScrapeJob.user_id == current_user.id)
        .order_by(ScrapeJob.created_at.desc())
        .limit(20)
        .all()
    )
    return jobs


@router.get("/jobs/{job_id}", response_model=ScrapeJobResponse)
def get_scrape_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Poll progress of a specific scrape job."""
    job = db.query(ScrapeJob).filter(
        ScrapeJob.id == job_id,
        ScrapeJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── Browser-extension endpoints (user-authed via cookie or Bearer header) ──────

@router.post("/ext/jobs", response_model=ScrapeJobResponse, status_code=201)
def create_ext_job(
    body: ExtJobCreate,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Create a scrape job for the browser extension. Unlike POST /jobs, this does
    NOT require stored LinkedIn credentials and does NOT dispatch to any
    server-side scraper — the extension scrapes in the user's own browser and
    posts leads back to /ext/jobs/{id}/leads.
    """
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Scraping requires an active ICP — leads are gated against it on ingest.
    if not _get_active_icp_inputs(db, current_user.id):
        raise HTTPException(
            status_code=400,
            detail="Define your Ideal Customer Profile (ICP) before scraping.",
        )

    job = ScrapeJob(
        user_id=current_user.id,
        query=body.query.strip(),
        pages_requested=0,
        status="running",
        scraped_count=0,
        leads_created=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/ext/jobs/{job_id}/leads")
def receive_ext_leads(
    job_id: int,
    body: InternalLeadsPayload,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Extension posts a batch of leads scraped from the user's own browser."""
    job = db.query(ScrapeJob).filter(
        ScrapeJob.id == job_id,
        ScrapeJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return _ingest_leads(db, job, body.leads)


@router.patch("/ext/jobs/{job_id}")
def update_ext_job(
    job_id: int,
    body: ExtJobPatch,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """Extension finalizes its job (e.g. status=completed)."""
    job = db.query(ScrapeJob).filter(
        ScrapeJob.id == job_id,
        ScrapeJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(job, field, value)

    db.commit()
    return {"ok": True}


# ── AI search query suggestions ───────────────────────────────────────────────

@router.post("/suggest-queries")
def suggest_search_queries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Proxy: fetch user's leads and ask the AI to suggest search queries."""
    leads = (
        db.query(Lead)
        .filter(Lead.assigned_to == current_user.id)
        .order_by(Lead.created_at.desc())
        .limit(20)
        .all()
    )

    leads_payload = [
        {
            "name": lead.name,
            "company": lead.company,
            "role": lead.role,
            "signals": lead.signals or [],
        }
        for lead in leads
    ]

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{AI_SERVICE_URL}/agent/search-queries",
                json={"leads": leads_payload},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
