from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):


    database_url: str = "sqlite:///./test.db"
    frontend_url: str = "http://localhost:3000"
    google_credentials_json: str = "{}"
    backend_url: str = "http://localhost:8000"
    ai_service_url: str = "http://localhost:8001"
    mail_username: Optional[str] = None
    mail_password: Optional[str] = None
    mail_from: Optional[str] = None
    mail_port: Optional[int] = None
    mail_server: Optional[str] = None
    mail_from_name: Optional[str] = None
    secret_key: str = "dev-secret-key-change-in-production"
    
    # MinIO Settings
    minio_endpoint: str = "minio:9000"  # Default to service name in Docker network
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "crm-emails"
    minio_secure: bool = False

    # Ollama Settings
    ollama_base_url: str = "http://localhost:11434"
    email_classifier_model: str = "llama3.2:3b"
    
    # Configurare pentru a citi si din fisier daca variabilele de mediu lipsesc
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", env_ignore_empty=True)

settings = Settings()