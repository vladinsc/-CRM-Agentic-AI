from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, Message, Client
from app.storage_service import StorageService
from app.auth import get_current_user, User

# 1. Initialize the router with a standard prefix
router = APIRouter(
    prefix="/api/projects/{project_id}/messages",
    tags=["Messages"] # This organizes your Swagger UI documentation beautifully
)

# 2. Initialize the storage service here
storage = StorageService()

# 3. Define the endpoint (notice the path is just "/", because the prefix handles the rest)
@router.post("/")
async def receive_new_message(
    project_id: int, 
    raw_html: str, 
    clean_text: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. SECURITY CHECK: Get the project, but JOIN the client to check ownership
    project = db.query(Project).join(Client).filter(
        Project.id == project_id,
        Client.user_id == current_user.id # STRICT ISOLATION HERE
    ).first()

    if not project:
        # We return 404 instead of 403 so hackers don't even know the project exists
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Upload to MinIO (Now isolated in the user's folder)
    minio_file_path = storage.upload_email(current_user.id, project.id, raw_html)
    
    # 3. Save to Postgres
    new_message = Message(
        project_id=project.id,
        sender_role="client",
        s3_file_path=minio_file_path
    )
    
    db.add(new_message)
    db.commit()
    
    return {"status": "success", "file_path": minio_file_path}