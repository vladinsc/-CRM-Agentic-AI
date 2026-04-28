from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import date
from app.database import get_db
from app.models import Lead, AgentActivity, User
from app.auth import get_current_user

router = APIRouter(prefix="/stats", tags=["stats"])


def _format_pipeline_value(total: float) -> str:
    """Formatează suma totală a pipeline-ului: €237K, €1.2M etc."""
    if total >= 1_000_000:
        return f"€{total / 1_000_000:.1f}M"
    if total >= 1_000:
        return f"€{int(total / 1_000)}K"
    return f"€{int(total)}"


@router.get("")
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returnează statistici pentru dashboard-ul userului curent:
    - hot_leads: leads cu score >= 80
    - ai_actions_today: activități AI create azi
    - pipeline_value: suma deal_value a tuturor lead-urilor
    """
    today = date.today()

    # Leads cu scor >= 80 (hot)
    hot_leads = (
        db.query(func.count(Lead.id))
        .filter(
            Lead.assigned_to == current_user.id,
            Lead.intent_score >= 80,
        )
        .scalar() or 0
    )

    # Activități AI create azi (JOIN prin lead → assigned_to)
    ai_actions_today = (
        db.query(func.count(AgentActivity.id))
        .join(Lead, AgentActivity.lead_id == Lead.id)
        .filter(
            Lead.assigned_to == current_user.id,
            cast(AgentActivity.created_at, Date) == today,
        )
        .scalar() or 0
    )

    # Suma pipeline (deal_value) — toate lead-urile userului
    pipeline_raw = (
        db.query(func.sum(Lead.deal_value))
        .filter(Lead.assigned_to == current_user.id)
        .scalar() or 0
    )

    return {
        "hot_leads": int(hot_leads),
        "ai_actions_today": int(ai_actions_today),
        "pipeline_value": _format_pipeline_value(float(pipeline_raw)),
        "pipeline_value_raw": float(pipeline_raw),
    }
