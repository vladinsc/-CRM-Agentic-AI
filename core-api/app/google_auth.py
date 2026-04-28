import os
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.models import User
from app.config import settings

# SCOPES defineste exact ce are voie sa faca aplicatia ta in contul userului. 
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_google_auth_url():
    """Genereaza link-ul pe care da click utilizatorul pentru a se loga cu Google."""
    flow = Flow.from_client_secrets_file(
        settings.google_secrets_path,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/api/auth/google/callback'
    )
    
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent' 
    )
    return auth_url

def get_gmail_service(user: User):
    """
    Foloseste token-ul din baza de date pentru a crea un client Google gata de folosire.
    """
    if not user.google_refresh_token:
        return None
        
    # Citim credentialele folosind calea din fisierul de configurare
    with open(settings.google_secrets_path, 'r') as file:
        client_config = json.load(file)
    
    creds = Credentials.from_authorized_user_info(
        info={
            "refresh_token": user.google_refresh_token,
            "client_id": client_config["web"]["client_id"],
            "client_secret": client_config["web"]["client_secret"],
        },
        scopes=SCOPES
    )
    
    service = build('gmail', 'v1', credentials=creds)
    return service