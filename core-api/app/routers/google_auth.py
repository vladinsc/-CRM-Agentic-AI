from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from app.database import get_db
from app.models import ConnectedAccount, User
from app.google_auth import get_connected_accounts_by_user_id, get_google_auth_url, SCOPES
from app.auth import get_current_user
from app.config import settings
from app.gmail_watch import process_gmail_updates, stop_gmail_watch
from fastapi import BackgroundTasks
from googleapiclient.discovery import build
import base64
import json
from pydantic import BaseModel

class PubSubMessage(BaseModel):
    data: str
    messageId: str
    publishTime: str

class PubSubPayload(BaseModel):
    message: PubSubMessage
    subscription: str

router = APIRouter(prefix="/api/auth/google", tags=["Google Authentication"])
REDIRECT_URI = f"{settings.frontend_url}/api/auth/google/callback"
@router.get("/login")
def google_login(response: Response):
    """
    Frontend-ul apeleaza acest endpoint pentru a primi URL-ul.
    """
    auth_url, code_verifier = get_google_auth_url()
    
    
    response.set_cookie(
        key="code_verifier",
        value=code_verifier,
        httponly=True,
        samesite="lax",
        max_age=300, # 5 minute
        secure=False # Pune True doar daca ai HTTPS
    )
    
    return {"auth_url": auth_url}
    

@router.get("/callback")
def google_callback(
    code: str, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ):

    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        code_verifier = request.cookies.get("code_verifier")
        
        client_config = json.loads(settings.google_credentials_json)
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Schimbam codul temporar primit de la Google pe token-uri reale de acces
        flow.fetch_token(code=code, code_verifier=code_verifier)
        credentials = flow.credentials
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        google_email = user_info.get("email")
        if not google_email:
            raise HTTPException(status_code=400, detail="Nu am putut obtine email-ul de Google")
        # Salvam Refresh Token-ul in Postgres.
        account = db.query(ConnectedAccount).filter(
            ConnectedAccount.user_id == current_user.id,
            ConnectedAccount.email == google_email
        ).first()
        
        if not account:
            """Daca nu avem deja un cont conectat cu acest email, cream unul nou."""
            if not credentials.refresh_token:
                # Google trimite refresh_token doar prima data cand user-ul da accept
                # Daca lipseste la o reconectare, inseamna ca trebuie sa revoci accesul din Google Settings
                raise HTTPException(status_code=400, detail="Lipseste Refresh Token. Revoca accesul aplicatiei din setarile Google si incearca iar.")
            account = ConnectedAccount(
                user_id=current_user.id,
                provider="google",
                email=google_email,
                refresh_token=credentials.refresh_token
            )
            db.add(account)
        else:
            # Daca exista deja, actualizam refresh_token-ul daca Google ni l-a trimis din nou
            if credentials.refresh_token:
                account.refresh_token = credentials.refresh_token
        
        db.commit()


        return {
            "status": "success", 
            "message": f"Contul {google_email} a fost conectat cu succes.",
            "google_email": google_email
        }
        
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        print(f"Eroare Callback: {error_msg}")
        if "Scope has changed" in error_msg or "invalid_grant" in error_msg or "Bad Request" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Permisiunea Gmail nu a fost acordată. "
                    "Urmează acești pași: "
                    "1) Du-te la console.cloud.google.com → APIs & Services → OAuth consent screen → Scopes → Add or remove scopes → adaugă 'https://www.googleapis.com/auth/gmail.modify'. "
                    "2) Revocă accesul aplicației de la myaccount.google.com/permissions. "
                    "3) Încearcă din nou reconectarea și bifează TOATE permisiunile."
                ),
            )
        raise HTTPException(status_code=400, detail=f"Eroare la procesarea callback-ului: {error_msg}")
    
@router.delete("/disconnect")
def google_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == current_user.id,
        ConnectedAccount.provider == "google",
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="No connected Google account found.")
    db.delete(account)
    db.commit()
    return {"message": "Google account disconnected successfully."}


@router.get("/get_connected_accounts")
def get_connected_accounts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = get_connected_accounts_by_user_id(current_user.id)
    return [{"id": acc.id, "email": acc.email, "provider": acc.provider, "is_watching": acc.is_watching} for acc in accounts]

@router.delete("/disconnect/{account_id}")
def disconnect_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Elimină un cont conectat. 
    1. Oprește watch-ul în Google Cloud (Pub/Sub).
    2. Șterge înregistrarea din baza de date.
    """
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.id == account_id,
        ConnectedAccount.user_id == current_user.id
    ).first()

    if not account:
        raise HTTPException(status_code=404, detail="Contul nu a fost găsit.")

    # Încercăm să oprim watch-ul înainte de ștergere
    # Chiar dacă eșuează (ex: token expirat), continuăm cu ștergerea locală
    stop_gmail_watch(account)

    try:
        db.delete(account)
        db.commit()
        return {"status": "success", "message": f"Contul {account.email} a fost deconectat."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Eroare la ștergerea contului: {str(e)}")

@router.post("/webhook")
async def gmail_webhook(payload: PubSubPayload, background_tasks: BackgroundTasks):
    """
    Acknowledge receipt of the Google Pub/Sub notification immediately.
    All processing is delegated to a background task.
    """
    # DEBUG PRINT: Verify request reachability
    print(f"\n[DEBUG] WEBHOOK RECEIVED: messageId={payload.message.messageId}")

    try:
        # Decodăm datele pentru a extrage informațiile necesare pentru background task
        message_bytes = base64.b64decode(payload.message.data)
        message_json = json.loads(message_bytes.decode('utf-8'))

        email_address = message_json.get('emailAddress')
        new_history_id = message_json.get('historyId')

        print(f"[DEBUG] DECODED: email={email_address}, historyId={new_history_id}")

        if email_address and new_history_id:
            # Pornim procesarea în background
            background_tasks.add_task(handle_gmail_webhook_background, email_address, new_history_id)

    except Exception as e:
        print(f"[DEBUG] ERROR decoding webhook: {str(e)}")

    return {"status": "accepted"}

def handle_gmail_webhook_background(email_address: str, new_history_id: str):
    """
    Background worker to find the account and trigger updates.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        account = db.query(ConnectedAccount).filter(
            ConnectedAccount.email == email_address
        ).first()

        if account:
            # Verificăm dacă avem noutăți reale
            if not account.last_history_id or int(new_history_id) > account.last_history_id:
                # Actualizăm punctul de referință
                account.last_history_id = int(new_history_id)
                db.commit()

                # Declanșăm procesarea mesajelor
                process_gmail_updates(account.id, int(new_history_id))
    except Exception as e:
        print(f"Eroare în background la procesarea webhook-ului Gmail: {str(e)}")
        db.rollback()
    finally:
        db.close()