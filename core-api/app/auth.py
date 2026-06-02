from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Cookie, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.config import settings


SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_user_flexible(
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Like get_current_user, but also accepts the JWT via an Authorization: Bearer
    header. Used by the browser-extension endpoints: the extension reads the
    httpOnly access_token cookie via chrome.cookies and forwards it as a Bearer
    header (the SameSite=Lax cookie won't auto-attach on cross-origin requests).
    """
    token = access_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _get_mail_conf() -> ConnectionConfig:
    """Build mail config lazily — only called when SMTP is actually configured."""
    return ConnectionConfig(
        MAIL_USERNAME=settings.mail_username or "",
        MAIL_PASSWORD=settings.mail_password or "",
        MAIL_FROM=settings.mail_from or "noreply@example.com",
        MAIL_PORT=settings.mail_port or 587,
        MAIL_SERVER=settings.mail_server or "localhost",
        MAIL_FROM_NAME=settings.mail_from_name or "CRM",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )

async def send_verification_email(email_to: str, token: str):

    verification_url = f"{settings.frontend_url}/verify-email?token={token}"

    html = f"""
    <html>
        <body>
            <p>Salut,</p>
            <p>Multumim ca te-ai inregistrat. Apasa pe butonul de mai jos pentru a-ti activa contul:</p>
            <a href="{verification_url}" 
               style="background-color: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
               Verifica Email
            </a>
            <p>Daca butonul nu functioneaza, copiaza acest link in browser:</p>
            <p>{verification_url}</p>
        </body>
    </html>
    """

    message = MessageSchema(
        subject="Verificare cont CRM",
        recipients=[email_to],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(_get_mail_conf())
    await fm.send_message(message)




def create_password_reset_token(email: str, current_password_hash: str) -> str:
    """Genereaza un JWT care expira 30 minute si contine semnatura parolei vechi."""
    expire = datetime.utcnow() + timedelta(minutes=30)
    
    # Luam ultimele 10 caractere din hash-ul curent pentru a invalida tokenul dupa schimbare
    hash_fragment = current_password_hash[-10:] if current_password_hash else ""
    
    to_encode = {
        "sub": email,
        "exp": expire,
        "hash_fragment": hash_fragment
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password_reset_token(token: str, current_password_hash: str) -> str | None:
    """Verifica daca token-ul e valid, nu a expirat si daca parola nu a fost deja schimbata."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_hash_fragment = payload.get("hash_fragment")
        
        # Verificam daca fragmentele se potrivesc
        current_fragment = current_password_hash[-10:] if current_password_hash else ""
        
        if email is None or token_hash_fragment != current_fragment:
            return None
            
        return email
    except JWTError:
        print("Error occurred while decoding JWT token")
        return None
    
def create_email_verification_token(email: str) -> str:

    """Genereaza un JWT pentru validarea email-ului, valabil 24 de ore."""
    expire = datetime.utcnow() + timedelta(hours=24)
    
    # Adaugam si un "type" ca sa fim siguri ca tokenul nu e folosit pentru altceva (ex: resetare parola)
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": "email_verification" 
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



async def send_reset_password_email(email_to: str, token: str):
    # Link-ul catre pagina din Frontend (Next.js) unde utilizatorul va introduce parola noua
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"

    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <p>Salut,</p>
            <p>Am primit o cerere pentru resetarea parolei asociate acestui cont.</p>
            <p>Apasa pe butonul de mai jos pentru a alege o parola noua. <strong>Acest link este valabil timp de 1 ora.</strong></p>
            <a href="{reset_url}" 
               style="background-color: #ef4444; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px; margin-bottom: 10px;">
               Reseteaza Parola
            </a>
            <p>Daca nu ai solicitat tu aceasta resetare, te rugam sa ignori acest email. Parola ta va ramane neschimbata.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin-top: 20px; margin-bottom: 20px;">
            <p style="font-size: 12px; color: #666;">Daca butonul nu functioneaza, copiaza si lipeste acest link in browserul tau: <br>{reset_url}</p>
        </body>
    </html>
    """

    message = MessageSchema(
        subject="Resetare parola cont CRM",
        recipients=[email_to],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(_get_mail_conf())
    await fm.send_message(message)