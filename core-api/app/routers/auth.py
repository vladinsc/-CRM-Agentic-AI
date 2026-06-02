from jose import jwt, JWTError
from fastapi import APIRouter, Depends, HTTPException, Response, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_access_token, get_current_user,create_email_verification_token ,send_verification_email,create_password_reset_token,verify_password_reset_token, send_reset_password_email, SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_verified: bool = False

    class Config:
        from_attributes = True
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str



@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest, response: Response, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.config import settings
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    smtp_configured = bool(settings.mail_username and settings.mail_password)

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        is_verified=not smtp_configured,
    )
    db.add(user)
    db.commit()

    if smtp_configured:
        verification_token = create_email_verification_token(body.email)
        background_tasks.add_task(send_verification_email, user.email, verification_token)

    db.refresh(user)

    # Set access token cookie so the user is logged in immediately after register
    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
    )

    return user

class VerifyTokenRequest(BaseModel):
    token: str

@router.post("/verify-email")
def verify_user_email(payload: VerifyTokenRequest, db: Session = Depends(get_db)):
    try:
            # Decodam si validam token-ul matematic
            payload_data = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload_data.get("sub")
            token_type = payload_data.get("type")

            # Ne asiguram ca token-ul este corect si este destinat verificarii emailului
            if email is None or token_type != "email_verification":
                raise HTTPException(status_code=400, detail="Token invalid")

    except JWTError:
        raise HTTPException(status_code=400, detail="Token invalid sau a expirat valabilitatea de 24h.")

    # Cautam utilizatorul dupa email-ul din token
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu exista.")

    # Daca da click pe link de doua ori (Replay Attack), nu e nicio problema de securitate
    # Pur si simplu ii spunem ca este deja verificat
    if user.is_verified:
        return {"message": "Contul tau este deja activat. Te poti autentifica."}

    # Activam contul
    user.is_verified = True
    db.commit()

    return {"message": "Cont verificat cu succes! Te poti autentifica."}

@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Contul nu este verificat. Te rugam sa verifici emailul.")

    token = create_access_token({"sub": str(user.id)})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == payload.email).first()
    
    if not user:
        return {"message": "Daca adresa exista in sistem, vei primi un email cu pasii de resetare."}

    # Generam JWT-ul
    token = create_password_reset_token(user.email, user.hashed_password)

    # Trimitem email-ul cu token-ul JWT
    background_tasks.add_task(send_reset_password_email, user.email, token)

    return {"message": "Daca adresa exista in sistem, vei primi un email cu pasii de resetare."}



@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    # 1. Decodam JWT-ul DOAR pentru a afla email-ul (fara verificare completa inca)
    try:
        # Ignoram verificarea expirarii pentru o secunda, doar ca sa citim email-ul
        unverified_payload = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False, "verify_exp": False})
        email = unverified_payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=400, detail="Token complet invalid.")

    # 2. Cautam userul in DB
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu exista.")

    # 3. Verificam token-ul real (aici se face magia: verifica timpul si hash-ul parolei)
    verified_email = verify_password_reset_token(payload.token, user.hashed_password)
    if not verified_email:
        raise HTTPException(status_code=400, detail="Token invalid, expirat sau parola a fost deja schimbata.")

    # 4. Totul e OK, schimbam parola
    user.hashed_password = hash_password(payload.new_password)
    db.commit()

    return {"message": "Parola a fost resetata cu succes!"}