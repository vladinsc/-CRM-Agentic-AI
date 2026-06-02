import os
import logging
import threading
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
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
    error_message: Optional[str] = None


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


def _icp_match_fields(name: str, company: str, role: str, icp_inputs: dict) -> dict:
    """Ask the ai-service whether a lead fits the ICP. Fail-closed on error."""
    payload = {
        "lead": {"name": name, "company": company, "role": role},
        "icp": icp_inputs,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{AI_SERVICE_URL}/agent/icp-match", json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.warning(f"ICP-match call failed for '{name}': {e}")
        # Fail-closed: if the agent is unreachable, mark as non-match (reviewable)
        # rather than silently flooding the pipeline.
        return {"match": False, "score": 0, "reasoning": "ICP match unavailable."}


def _ingest_leads(db: Session, job: ScrapeJob, leads: list["ScrapedLeadItem"]) -> dict:
    """
    Persist a batch of scraped leads quickly, then process ICP-matching + research
    ASYNCHRONOUSLY. ICP-match is an LLM call (~10s each); doing it inline would make
    a 25-lead page take minutes and time out the request. Instead we:
      1. dedup (in-batch + against the DB) and create leads as status='pending_icp'
      2. return immediately with how many were queued
      3. a background worker runs ICP-match per lead -> status 'new' (+research) or
         'rejected_icp', updating the job counts as it goes.
    """
    user_id = job.user_id

    queued_ids: list[int] = []
    skipped = 0
    seen_keys: set[str] = set()   # in-batch dedup (same person twice in one POST)

    for item in leads:
        if not item.name:
            skipped += 1
            continue

        # In-batch dedup key
        batch_key = (item.profile_url or "").strip() or f"{item.name}|{item.company}"
        if batch_key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(batch_key)

        # Cross-batch dedup: linkedin_url
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

        note = "Scraped from LinkedIn Sales Navigator"
        if item.location:
            note += f" · {item.location}"

        lead = Lead(
            name=item.name,
            company=item.company or "—",
            role=item.title or "—",
            email=f"scraped_li_{uuid4().hex[:8]}@placeholder.invalid",
            last_activity_description=note,
            linkedin_url=item.profile_url,
            company_url=item.company_url,
            status="pending_icp",
            assigned_to=user_id,
        )
        db.add(lead)
        db.flush()
        queued_ids.append(lead.id)

    job.scraped_count = (job.scraped_count or 0) + len(queued_ids) + skipped
    db.commit()

    # Hand the queued leads to a background worker (ICP-match + research).
    if queued_ids:
        threading.Thread(
            target=_process_scraped_leads,
            args=(queued_ids, user_id, job.id),
            daemon=True,
        ).start()

    return {"queued": len(queued_ids), "skipped": skipped,
            "accepted": len(queued_ids)}  # 'accepted' kept for backward-compat


def _process_scraped_leads(lead_ids: list[int], user_id: int, job_id: int) -> None:
    """
    Background worker: for each queued lead, run ICP-match (LLM). Matches become
    status='new' and are researched; non-matches become 'rejected_icp'. Runs off
    the request path so ingest returns instantly. Uses its own DB session.
    """
    db = SessionLocal()
    try:
        icp_inputs = _get_active_icp_inputs(db, user_id)
        for lead_id in lead_ids:
            # Honor cancellation: if the job was cancelled (or deleted), stop and
            # leave the remaining leads as 'pending_icp' (already saved).
            job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
            if not job or job.status in ("cancelled", "failed"):
                logger.info(f"Job {job_id} cancelled/gone — stopping lead processing.")
                break

            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if not lead:
                continue

            if icp_inputs:
                match = _icp_match_fields(lead.name, lead.company, lead.role, icp_inputs)
            else:
                # No active ICP — accept (shouldn't happen: create_ext_job blocks this).
                match = {"match": True, "reasoning": ""}
            is_match = bool(match.get("match"))

            lead.status = "new" if is_match else "rejected_icp"
            if not is_match and match.get("reasoning"):
                lead.last_activity_description = (
                    (lead.last_activity_description or "") + f" · ICP mismatch: {match['reasoning']}"
                )

            if is_match:
                job.leads_created = (job.leads_created or 0) + 1
            db.commit()

            if is_match:
                # Research runs under the shared Ollama lock (see leads.py).
                _run_research_thread(lead_id)
    except Exception as e:
        logger.exception(f"Scraped-lead processing failed for job {job_id}: {e}")
    finally:
        db.close()


# ── Scrape job endpoints (read-only; jobs are created via /ext/jobs) ──────────

# A 'running' job with no progress for this long is considered orphaned (the
# extension tab/popup likely closed without finalizing) and auto-expired.
STALE_JOB_MINUTES = 10


def _expire_stale_jobs(db: Session, user_id: int) -> None:
    """Mark long-running jobs with no recent activity as failed (timed out)."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_JOB_MINUTES)
    stale = (
        db.query(ScrapeJob)
        .filter(
            ScrapeJob.user_id == user_id,
            ScrapeJob.status.in_(["running", "pending"]),
            ScrapeJob.started_at.isnot(None),
            ScrapeJob.started_at < cutoff,
        )
        .all()
    )
    if not stale:
        return
    for job in stale:
        job.status = "failed"
        job.error_message = "Timed out — the scrape did not finish (tab closed?)."
        job.completed_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/jobs", response_model=list[ScrapeJobResponse])
def list_scrape_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List scrape jobs for the current user (most recent first)."""
    _expire_stale_jobs(db, current_user.id)
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
        started_at=datetime.now(timezone.utc),
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


@router.post("/ext/jobs/{job_id}/cancel")
def cancel_ext_job(
    job_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Cancel a running scrape job. Marks it 'cancelled'; the background ICP-matching
    worker checks this status each iteration and stops, keeping leads found so far.
    """
    job = db.query(ScrapeJob).filter(
        ScrapeJob.id == job_id,
        ScrapeJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ("running", "pending"):
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True, "status": job.status}


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
        # The SearchQueryAgent loops over multiple tool-calling iterations on a
        # small local model; a single run can take ~50-90s, and it may queue
        # behind other agents on the shared Ollama lock. Allow generous time.
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{AI_SERVICE_URL}/agent/search-queries",
                json={"leads": leads_payload},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"AI service unavailable: {str(e)}")
