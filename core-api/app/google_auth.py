import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.models import ConnectedAccount
from app.config import settings
from app.database import get_db
from google.auth.transport.requests import Request as GoogleRequest

# SCOPES defineste exact ce are voie sa faca aplicatia ta in contul userului. 
SCOPES = ['https://www.googleapis.com/auth/gmail.modify','https://www.googleapis.com/auth/userinfo.email', # <--- Permisiune pentru email
    'openid']
REDIRECT_URI = f"{settings.frontend_url}/api/auth/google/callback"

def get_google_auth_url():
    """Genereaza link-ul pe care da click utilizatorul pentru a se loga cu Google."""
    client_config = json.loads(settings.google_credentials_json)
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    
    return auth_url, flow.code_verifier

def get_gmail_service(account: ConnectedAccount):
    """
    Foloseste token-ul din baza de date pentru a crea un client Google gata de folosire.
    """
    """
    Creează un client Google folosind refresh token-ul.
    Detectează automat dacă fișierul de secrete este de tip 'web' sau 'installed'.
    """
    if not account or not account.refresh_token:
        print("Eroare: Contul nu are un refresh token valid.")
        return None
        
    try:
        client_config = json.loads(settings.google_credentials_json)
            
        # DETECTARE AUTOMATĂ: Verificăm dacă avem "web" sau "installed"
        # Aici era problema ta (KeyError)
        root_key = "web" if "web" in client_config else "installed"
        
        if root_key not in client_config:
            print("Eroare: Configurația Google nu are o structură validă.")
            return None

        # Extragem datele dinamice
        info = {
            "refresh_token": account.refresh_token,
            "client_id": client_config[root_key]["client_id"],
            "client_secret": client_config[root_key]["client_secret"],
        }
        
        creds = Credentials.from_authorized_user_info(
            info=info,
            scopes=SCOPES
        )

        # PAS CRITIC: Forțăm un refresh dacă token-ul de acces este expirat
        # Fără asta, apelurile API vor da eroare 401 după 60 de minute
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            # Opțional: poți salva noul access_token în DB dacă vrei, 
            # dar refresh_token-ul e suficient pentru a genera unul nou mereu.

        service = build('gmail', 'v1', credentials=creds)
        return service
    except json.JSONDecodeError:
        print("Eroare: Variabila google_credentials_json nu conține un JSON valid.")
        return None
    except Exception as e:
        print(f"Eroare neprevăzută la crearea serviciului Gmail: {e}")
        return None

def get_connected_accounts_by_user_id(user_id: int):
    """
    Functie helper pentru a lua toate conturile conectate ale unui utilizator.
    In cazul nostru, ne intereseaza doar cele Google, dar putem extinde usor pentru alti provideri.
    """
  
    
    db = next(get_db())
    accounts = db.query(ConnectedAccount).filter_by(user_id=user_id, provider="google").all()
    return accounts
