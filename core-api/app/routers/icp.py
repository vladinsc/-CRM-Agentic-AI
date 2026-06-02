from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.database import get_db
from app.models import ICPBlueprint
from app.auth import get_current_user

router = APIRouter(prefix="/icp", tags=["icp"])

class ICPCreate(BaseModel):
    target_persona: str
    target_company: str
    core_pain: str
    trigger_event: str
    value_proposition: str

class ICPResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    raw_inputs: Dict[str, str]
    structured_data: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

@router.post("/", response_model=ICPResponse)
def create_icp(
    payload: ICPCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Set existing ICPs to inactive for this user
    db.query(ICPBlueprint).filter(
        ICPBlueprint.user_id == current_user.id
    ).update({"is_active": False})

    new_icp = ICPBlueprint(
        user_id=current_user.id,
        raw_inputs=payload.model_dump(),
        is_active=True
    )
    db.add(new_icp)
    db.commit()
    db.refresh(new_icp)
    return new_icp

@router.get("/", response_model=Optional[ICPResponse])
def get_active_icp(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(ICPBlueprint).filter(
        ICPBlueprint.user_id == current_user.id,
        ICPBlueprint.is_active == True  # noqa: E712
    ).first()
