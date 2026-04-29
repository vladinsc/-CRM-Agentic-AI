from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from app.database import get_db
from app.models import User
from app.google_auth import get_google_auth_url, SCOPES
from app.auth import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/auth/google", tags=["Google Authentication"])
REDIRECT_URI = f"{settings.frontend_url}/api/auth/google/callback"
@router.get("/login")
def google_login():
    """
    Frontend-ul apeleaza acest endpoint pentru a primi URL-ul.
    """
    auth_url = get_google_auth_url()
    return {"auth_url": auth_url}

@router.get("/callback")
def google_callback(
    code: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dupa logare, Google face redirect inapoi aici, atasand parametrul ?code=...
    """
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        flow = Flow.from_client_secrets_file(
            settings.google_secrets_path,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Schimbam codul temporar primit de la Google pe token-uri reale de acces
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Salvam Refresh Token-ul in Postgres.
        if credentials.refresh_token:
            current_user.google_refresh_token = credentials.refresh_token
            db.commit()

        return {"status": "success", "message": "Contul de Gmail a fost conectat si token-ul a fost salvat."}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Eroare la procesarea callback-ului: {str(e)}")