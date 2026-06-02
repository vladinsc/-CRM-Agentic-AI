import asyncio
from sqlalchemy.orm import Session
from app.models import ConnectedAccount, Email
from app.database import SessionLocal
from app.google_auth import get_gmail_service
from app.services.ai_classifier import classify_incoming_email


def update_gmail_watch_state(account: ConnectedAccount, db: Session, activate: bool = True):
    service = get_gmail_service(account)
    if not service:
        return None

    if not activate:
        stop_gmail_watch(account)
        return account.last_history_id

    # Topic-ul tău din Google Cloud (folosește formatul complet)
    topic_name = "projects/emailspamdetector-490413/topics/gmail-trigger"
    request = {
        'labelIds': ['INBOX'], # Monitorizăm doar Inbox-ul pentru a evita spam-ul de notificări
        'topicName': topic_name
    }

    # Pornim monitorizarea
    watch_response = service.users().watch(userId='me', body=request).execute()

    # Salvăm historyId inițial pentru a avea un punct de referință
    return watch_response.get('historyId')

def stop_gmail_watch(account: ConnectedAccount):
    """
    Stops receiving notifications for the given Gmail account.
    This tells Google Cloud Pub/Sub to stop sending triggers.
    """
    service = get_gmail_service(account)
    if not service:
        return False
    try:
        service.users().stop(userId='me').execute()
        return True
    except Exception as e:
        print(f"Eroare la oprirea watch-ului Gmail pentru {account.email}: {e}")
        return False

def process_gmail_updates(account_id: int, new_history_id: int):
    """
    Background task to fetch and process Gmail history updates.
    Uses its own DB session to avoid connection leaks.
    """
    db = SessionLocal()
    try:
        account = db.query(ConnectedAccount).filter(ConnectedAccount.id == account_id).first()
        if not account:
            return

        service = get_gmail_service(account)
        if not service:
            return

        if not account.last_history_id:
            account.last_history_id = new_history_id
            db.commit()
            return

        # 1. Cerem lista de mesaje noi de la ultimul ID salvat
        try:
            history = service.users().history().list(
                userId='me', 
                startHistoryId=account.last_history_id
            ).execute()
        except Exception as e:
            print(f"Eroare la listarea history: {e}")
            return

        changes = history.get('history', [])

        for change in changes:
            if 'messagesAdded' in change:
                for msg_item in change['messagesAdded']:
                    try:
                        msg_id = msg_item['message']['id']

                        # 2. Luăm detaliile email-ului
                        message = service.users().messages().get(userId='me', id=msg_id).execute()

                        # Extragem expeditorul și subiectul
                        headers = message['payload']['headers']
                        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown")
                        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")
                        snippet = message.get('snippet')

                        print(f"Email nou de la {sender}: {subject}")

                        # Clasificăm emailul cu AI
                        try:
                            classification = asyncio.run(
                                classify_incoming_email(subject, snippet or "")
                            )
                            print(f"[Classifier] is_worth_saving={classification.is_worth_saving} score={classification.confidence_score}")

                            # Dacă merită salvat, îl scriem în DB
                            if classification.is_worth_saving:
                                # Verificăm să nu salvăm duplicate
                                existing = db.query(Email).filter(Email.email_id == msg_id).first()
                                if not existing:
                                    email_record = Email(
                                        user_id=account.user_id,
                                        email_id=msg_id,
                                        subject=subject,
                                        s3_path=f"gmail/{msg_id}",
                                        ai_reasoning=classification.reasoning,
                                        classification_score=classification.confidence_score,
                                    )
                                    db.add(email_record)
                        except Exception as clf_e:
                            print(f"[Classifier] Eroare la clasificare: {clf_e}")
                    except Exception as msg_e:
                        print(f"Eroare la procesarea mesajului individual: {msg_e}")

        # 4. Update historyId pentru data viitoare
        account.last_history_id = new_history_id
        db.commit()
    except Exception as e:
        print(f"Eroare generală în process_gmail_updates: {e}")
        db.rollback()
    finally:
        db.close()