from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.database import get_db
from app.models import AgentActivity, Lead, User
from app.auth import get_current_user

router = APIRouter(prefix="/activity", tags=["activity"])


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # action_type mapează pe tipurile din frontend Activity interface
    type: str
    message: str
    leadName: str
    timestamp: datetime
    status: str

    @classmethod
    def from_orm_activity(cls, activity: AgentActivity) -> "ActivityResponse":
        return cls(
            id=activity.id,
            type=activity.action_type,
            message=activity.message,
            leadName=activity.lead_name,
            timestamp=activity.created_at,
            status=activity.status,
        )


@router.get("", response_model=list[ActivityResponse])
def list_activity(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returnează cele mai recente activități AI pentru lead-urile userului curent.
    Filtrate prin JOIN: agent_activities → leads → assigned_to = current_user.id
    """
    activities = (
        db.query(AgentActivity)
        .join(Lead, AgentActivity.lead_id == Lead.id)
        .filter(Lead.assigned_to == current_user.id)
        .order_by(AgentActivity.created_at.desc())
        .limit(limit)
        .all()
    )
    return [ActivityResponse.from_orm_activity(a) for a in activities]
